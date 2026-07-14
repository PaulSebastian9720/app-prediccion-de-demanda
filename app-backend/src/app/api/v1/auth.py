"""Rutas de autenticacion: registro, login, refresh, logout, perfil."""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import Settings, get_settings
from app.core.rate_limit import limiter
from app.db.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return user_agent, ip


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo usuario",
    description="Crea una cuenta con rol `user`. El correo debe ser unico.",
    responses={409: {"description": "El correo ya esta registrado."}},
)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> User:
    return await auth_service.register_user(
        db, email=payload.email, password=payload.password, full_name=payload.full_name
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesion",
    description="Valida credenciales y emite un access token (JWT, 15 min) y un refresh "
    "token (opaco, 7 dias). Limitado a pocos intentos por minuto.",
    responses={401: {"description": "Correo o contrasena incorrectos."}},
)
@limiter.limit(get_settings().rate_limit_auth)
async def login(
    request: Request,
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    user = await auth_service.authenticate_user(db, email=payload.email, password=payload.password)
    user_agent, ip = _client_meta(request)
    access_token, refresh_token, expires_in = await auth_service.issue_token_pair(
        db, user=user, settings=settings, user_agent=user_agent, ip_address=ip
    )
    return TokenResponse(
        access_token=access_token, refresh_token=refresh_token, expires_in=expires_in
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotar tokens",
    description="Intercambia un refresh token valido por un nuevo par access+refresh. "
    "El refresh token usado queda revocado (rotacion de un solo uso).",
    responses={401: {"description": "Refresh token invalido, expirado o ya revocado."}},
)
async def refresh(
    request: Request,
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    user_agent, ip = _client_meta(request)
    access_token, refresh_token, expires_in = await auth_service.rotate_refresh_token(
        db,
        raw_refresh_token=payload.refresh_token,
        settings=settings,
        user_agent=user_agent,
        ip_address=ip,
    )
    return TokenResponse(
        access_token=access_token, refresh_token=refresh_token, expires_in=expires_in
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cerrar sesion",
    description="Revoca el refresh token indicado. Requiere un access token valido.",
)
async def logout(
    payload: LogoutRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> None:
    await auth_service.revoke_refresh_token(db, raw_refresh_token=payload.refresh_token)


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cerrar todas las sesiones",
    description="Revoca todos los refresh tokens activos del usuario autenticado "
    "(util ante sospecha de compromiso de la cuenta).",
)
async def logout_all(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
) -> None:
    await auth_service.revoke_all_sessions(db, user_id=user.id)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Perfil del usuario autenticado",
)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
