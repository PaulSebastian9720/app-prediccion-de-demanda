"""Fixtures de integracion: base de datos de test real (Postgres), cliente HTTP
contra la app real via ASGI (sin levantar un proceso), y helpers de autenticacion.

La base de datos de test (`<db>_test`) se crea y destruye una vez por sesion de
pytest; las tablas se truncan despues de cada test para aislar los casos.
"""

from collections.abc import AsyncIterator
from pathlib import Path

import asyncpg
import pandas as pd
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.api.deps import get_db, get_ml_registry
from app.core.config import get_settings
from app.core.constants import UserRole
from app.core.rate_limit import limiter
from app.core.security import hash_password
from app.db.base import Base
from app.db.models import *  # noqa: F401,F403 - registra todos los modelos en Base.metadata
from app.db.models.inventory_stock import InventoryStock
from app.db.models.product import Product
from app.db.models.user import User
from app.main import create_app
from app.ml.registry import MLModelRegistry
from app.schemas.sales_history import SalesRecordIn
from app.services.sales_history_service import upsert_records


def _admin_dsn(database_url: str) -> str:
    """DSN plano (sin `+asyncpg`) apuntando a la BD `postgres`, para crear/dropear la de test."""
    plain = database_url.replace("postgresql+asyncpg://", "postgresql://")
    prefix, _, _ = plain.rpartition("/")
    return f"{prefix}/postgres"


def _test_database_url(database_url: str) -> tuple[str, str]:
    prefix, _, dbname = database_url.rpartition("/")
    test_dbname = f"{dbname}_test"
    return f"{prefix}/{test_dbname}", test_dbname


def _resolve_model_dir(artifacts_root: Path) -> Path:
    """Igual que `tests/unit/conftest.py::model_artifacts_dir`: soporta tanto
    el layout plano legado como el versionado, sin depender de si
    `scripts/migrate_existing_model_to_versioned.py` ya se corrio."""
    models_dir = artifacts_root / "models"
    if models_dir.exists():
        versiones = sorted(p for p in models_dir.iterdir() if p.is_dir())
        if versiones:
            return versiones[0]
    return artifacts_root


@pytest.fixture(scope="session")
async def test_database_url() -> AsyncIterator[str]:
    settings = get_settings()
    test_url, test_dbname = _test_database_url(settings.database_url)
    admin_dsn = _admin_dsn(settings.database_url)

    conn = await asyncpg.connect(admin_dsn)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{test_dbname}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{test_dbname}"')
    finally:
        await conn.close()

    yield test_url

    conn = await asyncpg.connect(admin_dsn)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{test_dbname}" WITH (FORCE)')
    finally:
        await conn.close()


@pytest.fixture(scope="session")
async def test_engine(test_database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(test_database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def db_session_factory(test_engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def _truncate_tables(test_engine: AsyncEngine) -> AsyncIterator[None]:
    yield
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE'))


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    """El `Limiter` de slowapi es un singleton a nivel de modulo: sin este reset,
    los 5 intentos/minuto de `/auth/login` se agotarian entre tests distintos."""
    limiter.reset()


@pytest.fixture(scope="session")
def ml_registry() -> MLModelRegistry:
    settings = get_settings()
    registry = MLModelRegistry(_resolve_model_dir(settings.model_artifacts_dir))
    registry.load()
    return registry


@pytest.fixture
def app(db_session_factory: async_sessionmaker, ml_registry: MLModelRegistry) -> FastAPI:
    """Instancia de la app separada de `client` para que tests puntuales
    (ej. `test_retraining_endpoints.py`) puedan pisar `app.state.settings`
    -- ej. apuntar `model_artifacts_dir` a un `tmp_path` -- ANTES de que el
    `AsyncClient` empiece a usarla, sin tocar el resto de los tests."""
    application = create_app()
    application.state.session_factory = db_session_factory
    application.state.settings = get_settings()

    async def _override_get_db() -> AsyncIterator:
        async with db_session_factory() as session:
            yield session

    application.dependency_overrides[get_db] = _override_get_db
    application.dependency_overrides[get_ml_registry] = lambda: ml_registry
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as ac:
        yield ac


@pytest.fixture
async def user_headers(client: AsyncClient) -> dict[str, str]:
    await client.post(
        "/auth/register", json={"email": "test-user@example.com", "password": "TestPass123"}
    )
    r = await client.post(
        "/auth/login", json={"email": "test-user@example.com", "password": "TestPass123"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def admin_headers(
    client: AsyncClient, db_session_factory: async_sessionmaker
) -> dict[str, str]:
    async with db_session_factory() as db:
        db.add(
            User(
                email="test-admin@example.com",
                hashed_password=hash_password("AdminPass123"),
                role=UserRole.ADMIN,
            )
        )
        await db.commit()

    r = await client.post(
        "/auth/login", json={"email": "test-admin@example.com", "password": "AdminPass123"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def seeded_sales_history(
    db_session_factory: async_sessionmaker, ml_registry: MLModelRegistry
) -> None:
    """Carga el CSV historico completo en la BD de test (mismo dataset que produccion)."""
    settings = get_settings()
    csv_path = settings.model_artifacts_dir / "dataset_diario_series_temporales.csv"
    df = pd.read_csv(csv_path, parse_dates=["dia"])
    records = [
        SalesRecordIn(
            clasificador=row.clasificador,
            dia=row.dia.date(),
            cantidad_vendida=row.cantidad_vendida,
            precio_medio=row.precio_medio,
        )
        for row in df.itertuples(index=False)
    ]
    async with db_session_factory() as db:
        await upsert_records(db, records, set(ml_registry.clasificadores_validos))


@pytest.fixture
async def seeded_products_and_stock(
    db_session_factory: async_sessionmaker, ml_registry: MLModelRegistry
) -> None:
    """Precio/costo y stock fijos para los 9 clasificadores, independientes del
    historico de ventas: da numeros deterministas para tests de reportes/catalogo."""
    async with db_session_factory() as db:
        for clasificador in ml_registry.clasificadores_validos:
            db.add(
                Product(
                    clasificador=clasificador,
                    nombre_display=clasificador.title(),
                    precio_venta=10.0,
                    costo_reposicion=6.0,
                )
            )
            db.add(InventoryStock(clasificador=clasificador, stock_actual=50, stock_minimo=10))
        await db.commit()
