"""Modelo de eventos por etapa del pipeline de inferencia (trazabilidad granular)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import PipelineEventStatus
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.inference_log import InferenceLog


class PipelineEvent(Base):
    """Una fila por cada etapa (fetch_history, build_features, ...) de una prediccion.

    Se insertan en bloque junto con el `InferenceLog` padre al terminar la
    prediccion completa, no una escritura sincrona por etapa (ver
    `app.services.prediction_service`).
    """

    __tablename__ = "pipeline_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    inference_log_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inference_logs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[PipelineEventStatus] = mapped_column(
        Enum(
            PipelineEventStatus,
            name="pipeline_event_status",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    inference_log: Mapped["InferenceLog"] = relationship(back_populates="events")
