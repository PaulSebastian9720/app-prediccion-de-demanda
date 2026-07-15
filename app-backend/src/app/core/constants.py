"""Constantes y enumeraciones compartidas por toda la aplicacion."""

from enum import StrEnum


class UserRole(StrEnum):
    """Roles de usuario soportados por el sistema de autorizacion."""

    USER = "user"
    ADMIN = "admin"


class PredictionHorizon(StrEnum):
    """Horizonte temporal de una prediccion registrada en inference_logs."""

    DAY = "day"
    WEEK = "week"
    RANGE = "range"
    DAY_X = "day_x"


class RetrainingJobStatus(StrEnum):
    """Estado de un job de reentrenamiento."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class PipelineStage(StrEnum):
    """Etapas del pipeline de inferencia, registradas en pipeline_events."""

    FETCH_HISTORY = "fetch_history"
    BACKFILL_GAP = "backfill_gap"
    BUILD_FEATURES = "build_features"
    ENCODE_ALIGN = "encode_align"
    MODEL_INFERENCE = "model_inference"
    POSTPROCESS = "postprocess"
    EXPLANATION = "explanation"


class PipelineEventStatus(StrEnum):
    """Estado de un evento de pipeline."""

    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
