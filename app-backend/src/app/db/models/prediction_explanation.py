"""Modelo de la explicacion XAI generada para una prediccion de un unico dia.

Relacion 1:1 con `inference_logs`, en una tabla separada (no columnas en
`InferenceLog`) porque solo las predicciones de horizonte `day` generan una
explicacion: las de `week`/`range`/`day_x` nunca la tienen, y meterla como
columnas nulas en `inference_logs` dejaria vacia la inmensa mayoria de filas.
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.inference_log import InferenceLog


class PredictionExplanation(Base):
    """Explicacion en lenguaje natural + factores/ancla/confianza de un `InferenceLog`.

    `factores` es una lista de objetos `{factor, impacto_unidades, direccion,
    descripcion}` (ver `app.schemas.prediction.ExplanationFactor`), calculados
    por perturbacion real del pipeline (ver `app.ml.explainability`), no por
    conversion directa de las contribuciones SHAP/`pred_contribs` (que estan en
    escala log1p y no se pueden sumar linealmente a unidades).
    """

    __tablename__ = "prediction_explanations"

    inference_log_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inference_logs.id", ondelete="CASCADE"), primary_key=True
    )
    # Fecha y prediccion INDIVIDUAL del dia explicado -- no las del periodo.
    # Para horizonte DAY coinciden con las de `InferenceLog`, pero para DAY_X
    # `InferenceLog.fecha_objetivo`/`prediction_value` guardan el INICIO y el
    # TOTAL ACUMULADO del encadenado (ver `prediction_service.predict_range`),
    # no la fecha/cifra que describe `resumen` -- sin estas columnas, el
    # historial mostraria datos que no cuadran con la propia explicacion.
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    prediccion: Mapped[int] = mapped_column(Integer, nullable=False)
    resumen: Mapped[str] = mapped_column(String(2000), nullable=False)
    factores: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    # Ultimos ~14 dias de historial real (o real+relleno) antes del dia
    # explicado: `[{"fecha": "YYYY-MM-DD", "cantidad": int}, ...]`. Le da al
    # frontend datos para dibujar una tendencia simple (grafico de barras)
    # junto al texto -- la version "grafica" de la explicacion, no solo texto.
    historial_reciente: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    recomendacion: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dia_similar_fecha: Mapped[date | None] = mapped_column(Date, nullable=True)
    dia_similar_cantidad: Mapped[int | None] = mapped_column(Integer, nullable=True)
    margen_error_habitual: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Promedio historico de ESE mismo dia de la semana (ej. todos los
    # miercoles anteriores) -- solo aplica a /day y /day-x (un dia
    # especifico); en explicaciones de periodo (/week, /range) queda null.
    promedio_dia_semana: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Stock fisico actual (independiente del modelo de forecasting) de esta
    # categoria al momento de generar la explicacion, para comparar contra la
    # demanda predicha. Null si la categoria no tiene stock cargado todavia.
    stock_actual: Mapped[float | None] = mapped_column(Float, nullable=True)
    generado_por: Mapped[str] = mapped_column(String(16), nullable=False)  # "llm" | "fallback"
    modelo_llm: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    inference_log: Mapped["InferenceLog"] = relationship(back_populates="explanation")
