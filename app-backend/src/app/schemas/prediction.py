"""Schemas de prediccion (dia / semana / rango acumulado)."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.constants import PredictionHorizon


class PredictionDayRequest(BaseModel):
    """Solicitud de prediccion para un unico dia (pasado o futuro, cualquier fecha)."""

    clasificador: str = Field(..., examples=["PASEO_SUJECION"])
    fecha: date = Field(..., examples=["2026-07-09"])


class DailyPrediction(BaseModel):
    """Prediccion de un dia individual dentro de un rango acumulado."""

    fecha: date
    cantidad: int


class ExplanationFactor(BaseModel):
    """Un factor que ayuda a explicar la prediccion.

    `impacto_unidades` es el delta REAL en unidades, medido recalculando la
    prediccion con esta variable en su valor tipico (perturbacion) -- no una
    conversion directa de las contribuciones SHAP/`pred_contribs`, que estan
    en escala log1p y no se pueden sumar linealmente a unidades.
    """

    factor: str
    impacto_unidades: int
    direccion: Literal["sube", "baja"]
    descripcion: str


class DiaSimilar(BaseModel):
    """Dia historico con el patron de venta reciente mas parecido al dia predicho."""

    fecha: date
    cantidad: int


class ExplanationResponse(BaseModel):
    """Explicacion en lenguaje natural de una prediccion.

    Para /day y /day-x describe UN dia especifico (`factores` +
    `dia_similar` calculados por dia). Para /week y /range describe el
    PERIODO completo en conjunto -- una sola llamada al LLM sin importar
    cuantos dias tenga, no una por dia -- y en ese caso `factores`/`dia_similar`
    vienen vacios/null; el `resumen` ya trae el total, promedio, dia pico y
    comparacion con el periodo anterior.
    """

    resumen: str
    factores: list[ExplanationFactor]
    dia_similar: DiaSimilar | None = None
    margen_error_habitual: float | None = Field(
        default=None,
        description="MAE reciente (unidades) del clasificador, si hay suficientes "
        "predicciones ya vencidas para calcularlo.",
    )
    promedio_dia_semana: float | None = Field(
        default=None,
        description="Promedio historico de ventas en ESE mismo dia de la semana (solo "
        "/day y /day-x; null en explicaciones de periodo).",
    )
    stock_actual: float | None = Field(
        default=None,
        description="Stock fisico actual de la categoria al momento de generar la "
        "explicacion, para comparar contra la demanda predicha. Null si la categoria "
        "no tiene stock cargado todavia.",
    )
    recomendacion: str | None = None
    generado_por: Literal["llm", "fallback"]
    historial_reciente: list[DailyPrediction] = Field(
        default_factory=list,
        description="Ultimos ~14 dias de historial real (o real+relleno) antes de la "
        "fecha explicada, para dibujar una tendencia simple junto al texto.",
    )


class PredictionDayResponse(BaseModel):
    """Resultado de una prediccion diaria."""

    clasificador: str
    fecha: date
    cantidad_predicha: int = Field(..., description="Unidades vendidas predichas, >= 0.")
    dias_historial_usados: int
    model_version: str
    inference_log_id: uuid.UUID
    explicacion: ExplanationResponse | None = Field(
        default=None,
        description="Explicacion en lenguaje natural de por que se llego a este numero. "
        "Nunca bloquea la respuesta: si el LLM falla o tarda, se degrada a una "
        "explicacion generada por plantilla con los mismos datos verificados.",
    )


class PredictionHistoryItem(BaseModel):
    """Fila resumida del historial de predicciones con explicacion
    (`/predictions/history`) -- de cualquier horizonte."""

    inference_log_id: uuid.UUID
    clasificador: str
    horizonte: PredictionHorizon
    fecha: date = Field(
        ..., description="Dia individual (DAY/DAY_X) o inicio del periodo (WEEK/RANGE)."
    )
    cantidad_predicha: int = Field(
        ..., description="Cantidad individual (DAY/DAY_X) o total del periodo (WEEK/RANGE)."
    )
    resumen: str | None
    created_at: datetime


class PredictionHistoryDetail(BaseModel):
    """Detalle completo de una prediccion pasada, con su explicacion guardada."""

    inference_log_id: uuid.UUID
    clasificador: str
    horizonte: PredictionHorizon
    fecha: date
    cantidad_predicha: int
    model_version: str
    created_at: datetime
    explicacion: ExplanationResponse | None


class PredictionWeekRequest(BaseModel):
    """Solicitud de prediccion acumulada para 7 dias a partir de `fecha_inicio`."""

    clasificador: str = Field(..., examples=["PASEO_SUJECION"])
    fecha_inicio: date = Field(..., examples=["2026-07-09"])


class PredictionRangeRequest(BaseModel):
    """Solicitud de prediccion acumulada para un rango arbitrario de dias.

    `dias=7` equivale a `/predictions/week`; `dias=30` es util para estimar el
    stock necesario para "el mes siguiente" a partir de una fecha cualquiera.
    """

    clasificador: str = Field(..., examples=["PASEO_SUJECION"])
    fecha_inicio: date = Field(..., examples=["2026-07-09"])
    dias: int = Field(default=30, ge=1, le=90, examples=[30])


class PredictionRangeResponse(BaseModel):
    """Resultado de una prediccion acumulada (semana o rango arbitrario)."""

    clasificador: str
    fecha_inicio: date
    fecha_fin: date
    dias: int
    predicciones_diarias: list[DailyPrediction]
    total_periodo: int = Field(..., description="Suma de las predicciones diarias del periodo.")
    model_version: str
    inference_log_id: uuid.UUID
    explicacion: ExplanationResponse | None = Field(
        default=None,
        description="Explicacion EN CONJUNTO del periodo completo (una sola llamada al LLM, "
        "nunca por dia): total, promedio, dia pico y comparacion con el periodo anterior.",
    )


class ClasificadoresResponse(BaseModel):
    """Categorias de producto que el modelo reconoce (no se aceptan otras)."""

    clasificadores: list[str]


class PredictionDayXRequest(BaseModel):
    """Solicitud de prediccion para un dia objetivo concreto, encadenando desde hoy.

    No se especifica `fecha_inicio` ni `dias`: el backend decide el punto de
    partida (hoy, si `fecha_objetivo` es futura; la propia fecha, si ya paso).
    """

    clasificador: str = Field(..., examples=["PASEO_SUJECION"])
    fecha_objetivo: date = Field(..., examples=["2026-07-20"])


class PredictionDayXResponse(BaseModel):
    """Resultado de una prediccion 'Dia X': individual + acumulado, en una sola respuesta."""

    clasificador: str
    fecha_inicio: date = Field(
        ..., description="Punto de partida del encadenado (hoy, o `fecha_objetivo` si ya paso)."
    )
    fecha_objetivo: date
    dias_proyectados: int
    prediccion_individual: int = Field(
        ..., description="Unidades vendidas predichas SOLO para `fecha_objetivo`."
    )
    prediccion_acumulada: int = Field(
        ...,
        description="Suma de las predicciones diarias desde `fecha_inicio` hasta `fecha_objetivo`.",
    )
    predicciones_diarias: list[DailyPrediction]
    model_version: str
    inference_log_id: uuid.UUID
    explicacion: ExplanationResponse | None = Field(
        default=None,
        description="Explicacion en lenguaje natural de por que se llego a este numero para "
        "`fecha_objetivo`. Igual que en /predictions/day, nunca bloquea la respuesta.",
    )
