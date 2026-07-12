"""Punto de entrada de la aplicacion: factory `create_app()` + `lifespan`.

El modelo se carga una unica vez al arrancar (`lifespan`), en un hilo aparte
(`asyncio.to_thread`) para no bloquear el event loop durante la carga
CPU-bound de los artefactos, y se mantiene como una unica instancia en
`app.state.ml_registry` durante toda la vida del proceso.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import select

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, paint
from app.core.rate_limit import limiter
from app.db.models.model_version import ModelVersion
from app.db.session import create_engine, create_session_factory
from app.middleware.exception_handlers import register_exception_handlers
from app.middleware.logging_middleware import RequestLoggingMiddleware
from app.middleware.security_headers import BodySizeLimitMiddleware, SecurityHeadersMiddleware
from app.ml.registry import MLModelRegistry

logger = logging.getLogger("app.startup")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    # Resuelve la carpeta de artefactos a cargar: la version activa en
    # `model_versions` si ya se corrio la migracion a layout versionado
    # (`scripts/migrate_existing_model_to_versioned.py`), o el layout plano
    # legado como fallback (con un warning) si todavia no.
    artifacts_dir = settings.model_artifacts_dir
    async with session_factory() as db:
        activa = (
            await db.execute(select(ModelVersion).where(ModelVersion.is_active.is_(True)))
        ).scalar_one_or_none()
    if activa is not None:
        artifacts_dir = settings.model_artifacts_dir / activa.artifacts_dir
    else:
        logger.warning(
            "No hay ninguna version activa en 'model_versions' -- cargando el layout plano "
            "legado en %s. Corre 'scripts/migrate_existing_model_to_versioned.py' para "
            "activar el versionado.",
            artifacts_dir,
        )

    registry = MLModelRegistry(artifacts_dir)
    await asyncio.to_thread(registry.load)
    logger.info(
        "%s version=%s · %d categorias · %d features · lags=%s",
        paint("✔ Modelo XGBoost cargado y listo", "green", bold=True),
        registry.model_version,
        len(registry.clasificadores_validos),
        len(registry.feature_cols),
        registry.lags,
    )

    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.ml_registry = registry

    yield

    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "API para servir un modelo XGBoost de forecasting de ventas por categoria de "
            "producto, con autenticacion JWT (access + refresh token con rotacion), ingesta "
            "de historico de ventas (JSON/CSV/XLSX/XML) y logging dual (consola + PostgreSQL)."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    # El handler de RateLimitExceeded se registra en register_exception_handlers()
    # (mismo formato JSON consistente {"error": {...}} que el resto de errores).
    register_exception_handlers(app)

    # Starlette envuelve la app con el ULTIMO middleware agregado como el mas
    # externo. Se agregan en orden inverso al que deben ejecutarse para que el
    # orden real de procesamiento sea:
    #   SecurityHeaders -> BodySizeLimit -> CORS -> RateLimit -> RequestLogging -> rutas
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(BodySizeLimitMiddleware, max_body_size=settings.max_body_size_bytes)
    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
