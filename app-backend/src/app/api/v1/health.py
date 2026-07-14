"""Endpoint de salud del servicio."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_ml_registry
from app.ml.registry import MLModelRegistry
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Estado del servicio",
    description="Verifica que la API, el modelo y la base de datos esten operativos.",
)
async def health_check(
    db: AsyncSession = Depends(get_db),
    registry: MLModelRegistry = Depends(get_ml_registry),
) -> HealthResponse:
    try:
        await db.execute(text("SELECT 1"))
        database_status = "ok"
    except Exception:
        database_status = "error"

    return HealthResponse(
        status="ok",
        model_loaded=registry.is_loaded,
        database=database_status,
        timestamp=datetime.now(UTC),
    )
