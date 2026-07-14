"""Dependencias compartidas por los routers: sesion de BD, modelo ML, usuario actual, roles."""

import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.constants import UserRole
from app.core.exceptions import ForbiddenError, InvalidTokenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.models.user import User
from app.db.session import get_db_from_factory
from app.ml.registry import MLModelRegistry

bearer_scheme = HTTPBearer(auto_error=True)


async def get_db(request: Request) -> AsyncGenerator[AsyncSession]:
    """Provee una sesion de BD por request, usando la factory colgada en `app.state`."""
    async for session in get_db_from_factory(request.app.state.session_factory):
        yield session


def get_ml_registry(request: Request) -> MLModelRegistry:
    """Retorna la instancia unica del registro de modelo cargada en `lifespan()`."""
    return request.app.state.ml_registry


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """Decodifica el JWT del header `Authorization: Bearer <token>` y carga el usuario."""
    payload = decode_access_token(credentials.credentials, settings)

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise InvalidTokenError() from exc

    user = await db.get(User, user_id)
    if user is None:
        raise UnauthorizedError("El usuario del token ya no existe.")
    if not user.is_active:
        raise UnauthorizedError("La cuenta esta desactivada.")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Exige que el usuario autenticado tenga rol `admin`."""
    if user.role != UserRole.ADMIN:
        raise ForbiddenError("Se requiere rol de administrador.")
    return user
