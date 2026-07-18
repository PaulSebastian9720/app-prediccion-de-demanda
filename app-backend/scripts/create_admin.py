"""Crea (o promueve a admin) el usuario administrador inicial, de forma idempotente.

Usa `initial_admin_email` / `initial_admin_password` de la configuracion
(`.env`). Uso: `uv run python scripts/create_admin.py` (o `make create-admin`).
"""

import asyncio
import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.core.constants import UserRole
from app.core.security import hash_password
from app.db.models.user import User
from app.db.session import create_engine, create_session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    async with session_factory() as db:
        existing = (
            await db.execute(select(User).where(User.email == settings.initial_admin_email))
        ).scalar_one_or_none()

        if existing is not None:
            if existing.role != UserRole.ADMIN:
                existing.role = UserRole.ADMIN
                await db.commit()
                logger.info(
                    "Usuario existente '%s' promovido a admin.", settings.initial_admin_email
                )
            else:
                logger.info(
                    "El admin '%s' ya existe. Nada que hacer.", settings.initial_admin_email
                )
        else:
            admin = User(
                email=settings.initial_admin_email,
                hashed_password=hash_password(settings.initial_admin_password),
                full_name="Administrador",
                role=UserRole.ADMIN,
            )
            db.add(admin)
            await db.commit()
            logger.info("Admin creado: %s", settings.initial_admin_email)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
