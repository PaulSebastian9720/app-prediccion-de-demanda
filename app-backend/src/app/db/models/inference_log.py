"""Modelo de log de inferencias (predicciones) realizadas por el modelo."""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import PredictionHorizon
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.pipeline_event import PipelineEvent
    from app.db.models.prediction_explanation import PredictionExplanation


class InferenceLog(Base):
    """Una fila por cada prediccion (day/week/range) servida por la API."""

    __tablename__ = "inference_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    clasificador: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    fecha_objetivo: Mapped[date] = mapped_column(Date, nullable=False)
    horizonte: Mapped[PredictionHorizon] = mapped_column(
        Enum(
            PredictionHorizon,
            name="prediction_horizon",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    dias: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    prediction_value: Mapped[float] = mapped_column(Float, nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    events: Mapped[list["PipelineEvent"]] = relationship(
        back_populates="inference_log",
        cascade="all, delete-orphan",
        order_by="PipelineEvent.created_at",
    )
    explanation: Mapped["PredictionExplanation | None"] = relationship(
        back_populates="inference_log",
        cascade="all, delete-orphan",
        uselist=False,
    )
