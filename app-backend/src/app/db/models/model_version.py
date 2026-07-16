"""Modelo de una version entrenada y guardada del modelo XGBoost de forecasting.

Cada fila apunta a una carpeta bajo `artifacts/models/` (ver `app.ml.registry`
y `app.ml.training`) con los 4 archivos del modelo (pesos, transformer,
feature_cols, metadata) de esa version especifica. Solo una fila puede tener
`is_active=True` a la vez -- es la que `MLModelRegistry` tiene cargada en
memoria y la que sirve las predicciones en este momento.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.retraining_job import RetrainingJob


class ModelVersion(Base):
    """Una version guardada del modelo, con sus metricas y si esta activa."""

    __tablename__ = "model_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    version_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    fecha_entrenamiento: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Ruta relativa a `settings.model_artifacts_dir` (ej. "models/v001__20260713T123417"),
    # nunca absoluta -- portable entre entornos donde la raiz de artefactos difiera.
    artifacts_dir: Mapped[str] = mapped_column(String(255), nullable=False)
    # El `metadata["metricas"]` completo tal cual lo produce el entrenamiento:
    # {"validacion": {"MAE", "RMSE", "R2"}, "prueba": {"MAE", "RMSE", "R2"}}.
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retraining_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("retraining_jobs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # `foreign_keys` explicito: `model_versions` y `retraining_jobs` se
    # referencian mutuamente (`retraining_job_id` aqui, `model_version_id` en
    # `RetrainingJob`), asi que SQLAlchemy no puede inferir sola cual FK usar
    # para este lado de la relacion.
    retraining_job: Mapped["RetrainingJob | None"] = relationship(foreign_keys=[retraining_job_id])
