"""Schemas de metricas del modelo y del servicio."""

from typing import Any

from pydantic import BaseModel


class ModelMetricsResponse(BaseModel):
    """Metricas de desempeno del modelo, tal como quedaron registradas al entrenarlo."""

    mae: float
    rmse: float
    r2: float
    lags_usados: list[int]
    hiperparametros: dict[str, Any]
    n_features: int
    fecha_entrenamiento: str


class ServiceMetricsResponse(BaseModel):
    """Metricas operacionales del servicio en las ultimas 24 horas."""

    total_requests_24h: int
    total_predictions_24h: int
    avg_latency_ms_24h: float
    error_rate_24h: float
