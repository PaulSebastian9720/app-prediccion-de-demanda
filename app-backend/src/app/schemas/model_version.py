"""Schema de una version guardada del modelo (`model_versions`)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ModelVersionResponse(BaseModel):
    """Fila de `model_versions`, con sus metricas y si esta activa."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_number: int
    fecha_entrenamiento: datetime
    metrics: dict[str, Any]
    is_active: bool
    created_at: datetime
