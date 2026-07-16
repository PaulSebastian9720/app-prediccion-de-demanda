"""Schema de jobs de reentrenamiento."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.constants import RetrainingJobStatus


class RetrainingJobResponse(BaseModel):
    """Fila de `retraining_jobs`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: RetrainingJobStatus
    triggered_by_user_id: uuid.UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    model_version_id: uuid.UUID | None
    created_at: datetime
