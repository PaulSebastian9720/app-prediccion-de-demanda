"""Modelo de un job de reentrenamiento (ver `app.services.retraining_service`
para la orquestacion real: corre en background via `asyncio.to_thread`).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import RetrainingJobStatus
from app.db.base import Base


class RetrainingJob(Base):
    """Una fila por cada solicitud de reentrenamiento."""

    __tablename__ = "retraining_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    status: Mapped[RetrainingJobStatus] = mapped_column(
        Enum(
            RetrainingJobStatus,
            name="retraining_job_status",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=RetrainingJobStatus.PENDING,
        nullable=False,
    )
    triggered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Solo se enlaza cuando el entrenamiento termina (exitoso o no, ver
    # `retraining_service.run_retraining_job`): la version nueva se persiste
    # y se enlaza aunque no haya quedado activa (MAE peor que la actual).
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("model_versions.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
