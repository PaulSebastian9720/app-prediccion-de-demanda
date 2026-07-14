"""Schemas de consulta de logs (requests, inferencias y eventos de pipeline)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.core.constants import PipelineEventStatus, PredictionHorizon


class RequestLogResponse(BaseModel):
    """Fila de `request_logs`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    method: str
    path: str
    status_code: int
    duration_ms: float
    user_id: uuid.UUID | None
    ip_address: str
    user_agent: str | None
    created_at: datetime


class PipelineEventResponse(BaseModel):
    """Fila de `pipeline_events`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    stage: str
    status: PipelineEventStatus
    duration_ms: float | None
    message: str | None
    created_at: datetime


class InferenceLogResponse(BaseModel):
    """Fila de `inference_logs`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    clasificador: str
    fecha_objetivo: date
    horizonte: PredictionHorizon
    dias: int
    prediction_value: float
    duration_ms: float
    model_version: str
    created_at: datetime
