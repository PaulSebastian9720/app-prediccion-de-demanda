"""Consulta y administracion de usuarios."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.user import User
from app.schemas.user import UserUpdateRequest


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError(f"Usuario '{user_id}' no encontrado.")
    return user


async def list_users(db: AsyncSession, *, page: int, page_size: int) -> tuple[list[User], int]:
    total = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    stmt = (
        select(User)
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows), total


async def update_user(db: AsyncSession, user_id: uuid.UUID, payload: UserUpdateRequest) -> User:
    user = await get_user_by_id(db, user_id)
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.role is not None:
        user.role = payload.role
    await db.commit()
    await db.refresh(user)
    return user
