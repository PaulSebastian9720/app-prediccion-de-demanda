"""Logica de negocio de autenticacion: registro, login, rotacion y revocacion de sesiones."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import UserRole
from app.core.exceptions import (
    ConflictError,
    InvalidCredentialsError,
    TokenRevokedError,
    UnauthorizedError,
)
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User


async def register_user(
    db: AsyncSession, *, email: str, password: str, full_name: str | None
) -> User:
    """Crea un usuario nuevo con rol `user`. Levanta `ConflictError` si el correo ya existe."""
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"Ya existe un usuario con el correo '{email}'.")

    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=UserRole.USER,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, *, email: str, password: str) -> User:
    """Valida credenciales. Levanta `InvalidCredentialsError` / `UnauthorizedError`."""
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError()
    if not user.is_active:
        raise UnauthorizedError("La cuenta esta desactivada.")
    return user


async def issue_token_pair(
    db: AsyncSession,
    *,
    user: User,
    settings: Settings,
    user_agent: str | None,
    ip_address: str | None,
) -> tuple[str, str, int]:
    """Emite un nuevo par access+refresh y persiste el refresh token (hasheado)."""
    access_token = create_access_token(
        subject=str(user.id), role=user.role.value, settings=settings
    )
    raw_refresh, refresh_hash = generate_refresh_token()

    token_row = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(token_row)
    await db.commit()

    expires_in = settings.access_token_expire_minutes * 60
    return access_token, raw_refresh, expires_in


async def rotate_refresh_token(
    db: AsyncSession,
    *,
    raw_refresh_token: str,
    settings: Settings,
    user_agent: str | None,
    ip_address: str | None,
) -> tuple[str, str, int]:
    """Valida y revoca el refresh token recibido, emitiendo un nuevo par (rotacion)."""
    token_hash = hash_refresh_token(raw_refresh_token)
    token_row = (
        await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    ).scalar_one_or_none()

    if token_row is None:
        raise UnauthorizedError("Refresh token invalido.")
    if token_row.revoked or token_row.expires_at < datetime.now(UTC):
        raise TokenRevokedError()

    user = (await db.execute(select(User).where(User.id == token_row.user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise UnauthorizedError("El usuario asociado a este token ya no esta activo.")

    access_token = create_access_token(
        subject=str(user.id), role=user.role.value, settings=settings
    )
    raw_refresh, refresh_hash = generate_refresh_token()

    new_token_row = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(new_token_row)
    # Flush explicito: el INSERT del nuevo token debe ejecutarse antes del
    # UPDATE que referencia su id via `replaced_by_id` (FK), o Postgres
    # rechaza el UPDATE por violar la foreign key.
    await db.flush()

    token_row.revoked = True
    token_row.revoked_at = datetime.now(UTC)
    token_row.replaced_by_id = new_token_row.id

    await db.commit()

    expires_in = settings.access_token_expire_minutes * 60
    return access_token, raw_refresh, expires_in


async def revoke_refresh_token(db: AsyncSession, *, raw_refresh_token: str) -> None:
    """Revoca (logout) un refresh token especifico. Idempotente si ya estaba revocado."""
    token_hash = hash_refresh_token(raw_refresh_token)
    token_row = (
        await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    ).scalar_one_or_none()
    if token_row is None or token_row.revoked:
        return
    token_row.revoked = True
    token_row.revoked_at = datetime.now(UTC)
    await db.commit()


async def revoke_all_sessions(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    """Revoca todos los refresh tokens activos de un usuario (logout-all)."""
    stmt = select(RefreshToken).where(
        RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False)
    )
    tokens = (await db.execute(stmt)).scalars().all()
    now = datetime.now(UTC)
    for token in tokens:
        token.revoked = True
        token.revoked_at = now
    await db.commit()
