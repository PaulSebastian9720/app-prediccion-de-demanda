"""Rutas de gestion de usuarios (consulta y administracion)."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_admin
from app.core.exceptions import ForbiddenError
from app.db.models.user import User
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.user import UserResponse, UserUpdateRequest
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/",
    response_model=PaginatedResponse[UserResponse],
    summary="Listar usuarios",
    description="Solo administradores.",
    dependencies=[Depends(require_admin)],
)
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[UserResponse]:
    users, total = await user_service.list_users(db, page=page, page_size=page_size)
    total_pages = (total + page_size - 1) // page_size if total else 0
    return PaginatedResponse(
        items=[UserResponse.model_validate(u) for u in users],
        meta=PaginationMeta(
            page=page, page_size=page_size, total_items=total, total_pages=total_pages
        ),
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Consultar un usuario",
    description="Un administrador puede consultar cualquier usuario; un usuario normal solo su propio perfil.",
)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role.value != "admin" and current_user.id != user_id:
        raise ForbiddenError("No puedes consultar el perfil de otro usuario.")
    return await user_service.get_user_by_id(db, user_id)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Actualizar un usuario",
    description="Solo administradores. Permite cambiar nombre, estado y rol.",
    dependencies=[Depends(require_admin)],
)
async def update_user(
    user_id: uuid.UUID, payload: UserUpdateRequest, db: AsyncSession = Depends(get_db)
) -> User:
    return await user_service.update_user(db, user_id, payload)
