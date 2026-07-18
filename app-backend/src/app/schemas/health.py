"""Schema de health check."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Estado del servicio."""

    status: Literal["ok"]
    model_loaded: bool
    database: Literal["ok", "error"]
    timestamp: datetime
