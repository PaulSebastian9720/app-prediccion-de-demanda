"""Motor y sesiones asincronas de SQLAlchemy."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Crea el engine asincrono de SQLAlchemy a partir de la configuracion."""
    return create_async_engine(settings.database_url, pool_pre_ping=True, echo=False)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Crea la factory de sesiones asincronas asociada a un engine."""
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_db_from_factory(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession]:
    """Provee una sesion de BD por request, cerrandola al finalizar."""
    async with session_factory() as session:
        yield session
