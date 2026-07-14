"""Rutas de prediccion: dia individual, semana y rango acumulado arbitrario."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_ml_registry
from app.core.config import Settings, get_settings
from app.core.constants import PredictionHorizon
from app.core.exceptions import NotFoundError
from app.db.models.user import User
from app.ml.registry import MLModelRegistry
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.prediction import (
    ClasificadoresResponse,
    DailyPrediction,
    DiaSimilar,
    ExplanationFactor,
    ExplanationResponse,
    PredictionDayRequest,
    PredictionDayResponse,
    PredictionDayXRequest,
    PredictionDayXResponse,
    PredictionHistoryDetail,
    PredictionHistoryItem,
    PredictionRangeRequest,
    PredictionRangeResponse,
    PredictionWeekRequest,
)
from app.services import explanation_service, prediction_service

router = APIRouter(prefix="/predictions", tags=["predictions"])


def _to_explanation_response(
    snapshot: explanation_service.ExplanationSnapshot | None,
) -> ExplanationResponse | None:
    """Traduce el snapshot plano (ver `explanation_service.to_snapshot`) al
    schema anidado de respuesta. Unico punto de conversion, usado tanto por
    `/day` como por el historial, para que ambos vean exactamente lo mismo.

    Recibe un dict y no el ORM directamente: en `/day`, el `PredictionExplanation`
    ya fue persistido (commit) para cuando llega aqui, y `AsyncSession` expira
    sus atributos en el commit -- leerlos fuera de un `await` rompe con
    `MissingGreenlet`. El snapshot se congela ANTES de ese commit.
    """
    if snapshot is None:
        return None
    dia_similar = None
    fecha = snapshot["dia_similar_fecha"]
    cantidad = snapshot["dia_similar_cantidad"]
    if fecha is not None and cantidad is not None:
        dia_similar = DiaSimilar(fecha=fecha, cantidad=cantidad)
    return ExplanationResponse(
        resumen=snapshot["resumen"],
        factores=[ExplanationFactor(**factor) for factor in snapshot["factores"]],
        dia_similar=dia_similar,
        margen_error_habitual=snapshot["margen_error_habitual"],
        promedio_dia_semana=snapshot["promedio_dia_semana"],
        stock_actual=snapshot["stock_actual"],
        recomendacion=snapshot["recomendacion"],
        generado_por=snapshot["generado_por"],
        historial_reciente=[DailyPrediction(**dia) for dia in snapshot["historial_reciente"]],
    )


@router.post(
    "/day",
    response_model=PredictionDayResponse,
    summary="Predecir un dia",
    description="Predice las unidades vendidas de una categoria para cualquier fecha "
    "(pasada o futura), siempre que existan al menos 21 dias de historial previo. "
    "No esta limitado a 'manana': acepta cualquier fecha. Incluye una explicacion en "
    "lenguaje natural de por que se llego a ese numero (unico endpoint que la genera).",
    responses={422: {"description": "Historial insuficiente o clasificador desconocido."}},
)
async def predict_day(
    payload: PredictionDayRequest,
    db: AsyncSession = Depends(get_db),
    registry: MLModelRegistry = Depends(get_ml_registry),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
) -> PredictionDayResponse:
    prediccion, inference_log_id, explicacion_snapshot = await prediction_service.predict_day(
        db,
        registry,
        settings,
        clasificador=payload.clasificador,
        fecha=payload.fecha,
        user_id=user.id,
    )
    return PredictionDayResponse(
        clasificador=payload.clasificador,
        fecha=payload.fecha,
        cantidad_predicha=prediccion,
        dias_historial_usados=registry.historia_minima,
        model_version=registry.model_version,
        inference_log_id=inference_log_id,
        explicacion=_to_explanation_response(explicacion_snapshot),
    )


@router.post(
    "/day-x",
    response_model=PredictionDayXResponse,
    summary="Predecir un dia objetivo, encadenando desde hoy",
    description="Predice un dia concreto (ej. '20 de julio') sin que el llamador tenga que "
    "calcular ventanas: el backend encadena dia a dia desde hoy (o desde la propia fecha, si ya "
    "paso) hasta llegar ahi. Devuelve DOS numeros: `prediccion_individual` (solo ese dia) y "
    "`prediccion_acumulada` (la suma de todo el periodo recorrido).",
    responses={422: {"description": "Clasificador desconocido o fecha demasiado lejana."}},
)
async def predict_day_x(
    payload: PredictionDayXRequest,
    db: AsyncSession = Depends(get_db),
    registry: MLModelRegistry = Depends(get_ml_registry),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
) -> PredictionDayXResponse:
    (
        prediccion_individual,
        prediccion_acumulada,
        predicciones,
        fecha_inicio,
        inference_log_id,
        explicacion_snapshot,
    ) = await prediction_service.predict_day_x(
        db,
        registry,
        settings,
        clasificador=payload.clasificador,
        fecha_objetivo=payload.fecha_objetivo,
        user_id=user.id,
    )
    return PredictionDayXResponse(
        clasificador=payload.clasificador,
        fecha_inicio=fecha_inicio,
        fecha_objetivo=payload.fecha_objetivo,
        dias_proyectados=len(predicciones),
        prediccion_individual=prediccion_individual,
        prediccion_acumulada=prediccion_acumulada,
        predicciones_diarias=[DailyPrediction(fecha=f, cantidad=c) for f, c in predicciones],
        model_version=registry.model_version,
        inference_log_id=inference_log_id,
        explicacion=_to_explanation_response(explicacion_snapshot),
    )


async def _predict_range(
    db: AsyncSession,
    registry: MLModelRegistry,
    settings: Settings,
    user: User,
    clasificador: str,
    fecha_inicio: date,
    dias: int,
    horizonte: PredictionHorizon,
) -> PredictionRangeResponse:
    predicciones, total, inference_log_id, explicacion_snapshot = await prediction_service.predict_range(
        db,
        registry,
        settings,
        clasificador=clasificador,
        fecha_inicio=fecha_inicio,
        dias=dias,
        horizonte=horizonte,
        user_id=user.id,
        generar_explicacion=True,
    )
    return PredictionRangeResponse(
        clasificador=clasificador,
        fecha_inicio=predicciones[0][0],
        fecha_fin=predicciones[-1][0],
        dias=dias,
        predicciones_diarias=[DailyPrediction(fecha=f, cantidad=c) for f, c in predicciones],
        total_periodo=total,
        model_version=registry.model_version,
        inference_log_id=inference_log_id,
        explicacion=_to_explanation_response(explicacion_snapshot),
    )


@router.post(
    "/week",
    response_model=PredictionRangeResponse,
    summary="Predecir 7 dias acumulados",
    description="Encadena 7 predicciones diarias a partir de `fecha_inicio`, retroalimentando "
    "cada dia predicho como historial del siguiente. Equivale a `/range` con `dias=7`. Incluye "
    "una explicacion EN CONJUNTO del periodo (una sola llamada al LLM, no una por dia).",
)
async def predict_week(
    payload: PredictionWeekRequest,
    db: AsyncSession = Depends(get_db),
    registry: MLModelRegistry = Depends(get_ml_registry),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
) -> PredictionRangeResponse:
    return await _predict_range(
        db,
        registry,
        settings,
        user,
        payload.clasificador,
        payload.fecha_inicio,
        7,
        PredictionHorizon.WEEK,
    )


@router.post(
    "/range",
    response_model=PredictionRangeResponse,
    summary="Predecir un rango acumulado arbitrario",
    description="Generaliza `/week` a cualquier numero de dias (1-90). Util para estimar, "
    "por ejemplo, el stock necesario para el mes siguiente a partir de una fecha dada "
    "(`dias=30`). Incluye una explicacion EN CONJUNTO del periodo (una sola llamada al LLM, "
    "no una por dia).",
)
async def predict_range_endpoint(
    payload: PredictionRangeRequest,
    db: AsyncSession = Depends(get_db),
    registry: MLModelRegistry = Depends(get_ml_registry),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
) -> PredictionRangeResponse:
    return await _predict_range(
        db,
        registry,
        settings,
        user,
        payload.clasificador,
        payload.fecha_inicio,
        payload.dias,
        PredictionHorizon.RANGE,
    )


@router.get(
    "/clasificadores",
    response_model=ClasificadoresResponse,
    summary="Categorias reconocidas por el modelo",
    description="Lista las categorias validas de `clasificador`. No se aceptan otras al "
    "ingestar historico ni al predecir.",
)
async def list_clasificadores(
    registry: MLModelRegistry = Depends(get_ml_registry),
) -> ClasificadoresResponse:
    return ClasificadoresResponse(clasificadores=registry.clasificadores_validos)


@router.get(
    "/history",
    response_model=PaginatedResponse[PredictionHistoryItem],
    summary="Historial de todas las predicciones con explicacion",
    description="Predicciones pasadas de cualquier horizonte -- `/day`/`/day-x` (explicacion "
    "por dia) y tambien `/week`/`/range` (explicacion en conjunto del periodo) -- con el "
    "resumen de su explicacion guardada. Visible para cualquier usuario autenticado: es "
    "historial de consulta del equipo, no auditoria tecnica -- para eso esta "
    "`/logs/inferences` (solo administradores).",
)
async def list_prediction_history(
    clasificador: str | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> PaginatedResponse[PredictionHistoryItem]:
    rows, total = await prediction_service.list_prediction_history(
        db,
        clasificador=clasificador,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )
    total_pages = (total + page_size - 1) // page_size if total else 0
    return PaginatedResponse(
        items=[
            PredictionHistoryItem(
                inference_log_id=row.id,
                clasificador=row.clasificador,
                horizonte=row.horizonte,
                # `row.explanation.fecha`/`.prediccion` son la fecha y cifra que
                # describe el propio `resumen` (el dia individual en DAY/DAY_X,
                # el inicio y el total del periodo en WEEK/RANGE); `row.fecha_objetivo`/
                # `.prediction_value` en DAY_X/WEEK/RANGE guardan el INICIO y el TOTAL
                # ACUMULADO del encadenado (ver prediction_service.predict_range), que
                # no siempre coincide -- por eso se prefiere la explicacion cuando existe.
                fecha=row.explanation.fecha if row.explanation else row.fecha_objetivo,
                cantidad_predicha=(
                    row.explanation.prediccion if row.explanation else round(row.prediction_value)
                ),
                resumen=row.explanation.resumen if row.explanation else None,
                created_at=row.created_at,
            )
            for row in rows
        ],
        meta=PaginationMeta(
            page=page, page_size=page_size, total_items=total, total_pages=total_pages
        ),
    )


@router.get(
    "/history/{inference_log_id}",
    response_model=PredictionHistoryDetail,
    summary="Detalle de una prediccion pasada, con su explicacion guardada",
    description="Lee la explicacion ya persistida -- no vuelve a llamar al LLM ni recalcula "
    "nada, es una consulta directa a la base de datos. Funciona para cualquier horizonte "
    "(dia, semana, rango).",
    responses={404: {"description": "No existe una prediccion con ese id."}},
)
async def get_prediction_history_detail(
    inference_log_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> PredictionHistoryDetail:
    row = await prediction_service.get_prediction_detail(db, inference_log_id)
    if row is None:
        raise NotFoundError(f"No existe una prediccion con id '{inference_log_id}'.")
    return PredictionHistoryDetail(
        inference_log_id=row.id,
        clasificador=row.clasificador,
        horizonte=row.horizonte,
        fecha=row.explanation.fecha if row.explanation else row.fecha_objetivo,
        cantidad_predicha=(
            row.explanation.prediccion if row.explanation else round(row.prediction_value)
        ),
        model_version=row.model_version,
        created_at=row.created_at,
        explicacion=_to_explanation_response(
            explanation_service.to_snapshot(row.explanation) if row.explanation else None
        ),
    )
