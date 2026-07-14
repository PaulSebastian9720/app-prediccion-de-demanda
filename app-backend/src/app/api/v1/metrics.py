"""Rutas de metricas del modelo y del servicio."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_ml_registry, require_admin
from app.ml.registry import MLModelRegistry
from app.schemas.metrics import ModelMetricsResponse, ServiceMetricsResponse
from app.services import log_service

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get(
    "/model",
    response_model=ModelMetricsResponse,
    summary="Metricas de desempeno del modelo",
    description="MAE/RMSE/R2 registrados al entrenar el modelo, tal como quedaron en "
    "`metadata_modelo.json`.",
    dependencies=[Depends(get_current_user)],
)
async def model_metrics(
    registry: MLModelRegistry = Depends(get_ml_registry),
) -> ModelMetricsResponse:
    metadata = registry.metadata
    metricas_prueba = metadata["metricas"]["prueba"]
    return ModelMetricsResponse(
        mae=metricas_prueba["MAE"],
        rmse=metricas_prueba["RMSE"],
        r2=metricas_prueba["R2"],
        lags_usados=metadata["lags_usados"],
        hiperparametros=metadata["hiperparametros"],
        n_features=metadata["n_features"],
        fecha_entrenamiento=metadata["fecha_entrenamiento"],
    )


@router.get(
    "/service",
    response_model=ServiceMetricsResponse,
    summary="Metricas operacionales del servicio (ultimas 24h)",
    description="Solo administradores.",
    dependencies=[Depends(require_admin)],
)
async def service_metrics(db: AsyncSession = Depends(get_db)) -> ServiceMetricsResponse:
    return await log_service.get_service_metrics(db)
