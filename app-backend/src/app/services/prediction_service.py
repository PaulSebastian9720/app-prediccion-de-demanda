"""Orquesta el pipeline de prediccion e instrumenta cada etapa en `pipeline_events`.

Los eventos se acumulan en memoria durante la prediccion y se persisten en una
sola transaccion junto con el `InferenceLog` padre al finalizar, para no
penalizar la latencia con multiples escrituras sincronas a la base de datos.
Si la persistencia del log falla, solo se registra un `warning` en consola:
la respuesta al cliente nunca se sacrifica por un fallo de auditoria.
"""

import logging
import time
import uuid
from datetime import date

import pandas as pd
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.constants import PipelineEventStatus, PipelineStage, PredictionHorizon
from app.core.exceptions import DateTooFarError, UnknownClassifierError
from app.core.logging import paint
from app.db.models.inference_log import InferenceLog
from app.db.models.pipeline_event import PipelineEvent
from app.db.models.prediction_explanation import PredictionExplanation
from app.ml import features
from app.ml.registry import MLModelRegistry
from app.services import explanation_service, sales_history_service

# Logger dedicado ("app.ml.pipeline") para que la narrativa de la inferencia se
# distinga a simple vista del resto de logs y se pueda filtrar/silenciar aparte.
logger = logging.getLogger("app.ml.pipeline")

# Tope de dias que se pueden encadenar en una sola llamada a /predictions/day-x,
# para evitar cadenas de computo desmedidas por una fecha objetivo demasiado lejana.
MAX_DIAS_DAY_X = 180

# Color de cada etapa del pipeline, agrupado por naturaleza: azul=acceso a
# datos/BD, cian=preparacion de features, magenta=el modelo entrenado en si.
_STAGE_COLOR: dict[str, str] = {
    PipelineStage.FETCH_HISTORY: "blue",
    PipelineStage.BACKFILL_GAP: "blue",
    PipelineStage.BUILD_FEATURES: "cyan",
    PipelineStage.ENCODE_ALIGN: "cyan",
    PipelineStage.MODEL_INFERENCE: "magenta",
    PipelineStage.POSTPROCESS: "cyan",
    PipelineStage.EXPLANATION: "yellow",
}


def _log_header(horizonte: str, clasificador: str, objetivo: date, dias: int) -> None:
    """Linea de apertura de una prediccion (que categoria, que fecha, cuantos dias)."""
    dias_txt = f" · {dias} dias" if dias > 1 else ""
    logger.info(
        "%s %s · categoria=%s · objetivo=%s%s",
        paint("▶ PREDICCION", "white", bold=True),
        paint(str(horizonte), "white", bold=True),
        paint(clasificador, "yellow"),
        objetivo,
        dias_txt,
    )


def _log_footer(resultado: str, total_ms: float, model_version: str, log_id: uuid.UUID) -> None:
    """Linea de cierre: resultado, tiempo total, version del modelo y id de auditoria."""
    logger.info(
        "%s %s · total %s · modelo=%s · log_id=%s",
        paint("✔ RESULTADO", "green", bold=True),
        paint(resultado, "green", bold=True),
        paint(f"{total_ms:.1f} ms", "gray"),
        model_version,
        str(log_id)[:8],
    )


class _EventRecorder:
    """Acumula eventos de pipeline en memoria para persistirlos en una sola escritura."""

    def __init__(self) -> None:
        self.events: list[PipelineEvent] = []

    def record(
        self,
        stage: str,
        status: PipelineEventStatus,
        duration_ms: float | None,
        message: str | None = None,
    ) -> None:
        self.events.append(
            PipelineEvent(
                id=uuid.uuid4(),
                stage=stage,
                status=status,
                duration_ms=duration_ms,
                message=message,
            )
        )
        # Una linea legible y coloreada por etapa. El nombre de la etapa va en su
        # color; el detalle en texto normal; la duracion atenuada a la derecha.
        color = _STAGE_COLOR.get(stage, "gray")
        etapa = paint(f"{stage:<16}", color, bold=True)
        marca = "" if status == PipelineEventStatus.COMPLETED else paint(f"[{status}] ", "red")
        detalle = message or ""
        dur = paint(f"{duration_ms:6.1f} ms", "gray") if duration_ms is not None else ""
        logger.info("   %s %s%s   %s", etapa, marca, detalle, dur)


def _validate_clasificador(registry: MLModelRegistry, clasificador: str) -> None:
    if clasificador not in registry.clasificadores_validos:
        raise UnknownClassifierError(
            f"Clasificador desconocido: '{clasificador}'. Validos: {registry.clasificadores_validos}"
        )


async def _persist_inference_log(db: AsyncSession, inference_log: InferenceLog) -> None:
    try:
        db.add(inference_log)
        await db.commit()
        await db.refresh(inference_log)
    except Exception:
        await db.rollback()
        logger.warning("No se pudo persistir inference_log id=%s", inference_log.id, exc_info=True)


async def _persist_explanation(
    db: AsyncSession,
    inference_log_id: uuid.UUID,
    explanation: PredictionExplanation,
    event: PipelineEvent,
) -> None:
    """Persiste la explicacion XAI + su evento de pipeline en una transaccion
    PROPIA, separada de la del `InferenceLog` padre (ya confirmado para cuando
    se llama esto).

    Es deliberado que esto NO cascade en el mismo commit que `InferenceLog`:
    `AsyncSession` expira los atributos de TODOS los objetos de la sesion al
    hacer rollback, no solo los de la transaccion fallida. Si la explicacion
    se persistiera junto con el `InferenceLog` y algo fallara (p.ej. la tabla
    `prediction_explanations` no existe todavia por una migracion pendiente),
    el rollback tumbaria tambien el registro de la prediccion ya calculada, y
    el `inference_log_id` devuelto al endpoint quedaria en un objeto con
    atributos expirados -- leerlos despues rompe con
    `sqlalchemy.exc.MissingGreenlet`. Al recibir `inference_log_id` ya como un
    UUID plano (no el objeto ORM), este fallo queda contenido aqui.
    """
    try:
        explanation.inference_log_id = inference_log_id
        event.inference_log_id = inference_log_id
        db.add(explanation)
        db.add(event)
        await db.commit()
    except Exception:
        await db.rollback()
        logger.warning(
            "No se pudo persistir la explicacion del inference_log id=%s",
            inference_log_id,
            exc_info=True,
        )


async def _fetch_and_backfill_history(
    db: AsyncSession,
    registry: MLModelRegistry,
    clasificador: str,
    fecha_limite: date,
    recorder: _EventRecorder,
) -> pd.DataFrame:
    """Trae el historial real y, si hace falta, rellena huecos de calendario
    encadenando predicciones hasta dejar una serie diaria continua justo antes
    de `fecha_limite`.

    Sin este relleno, si el ultimo dato real no es exactamente el dia anterior
    a `fecha_limite` (ej. predecir "desde hoy" cuando la ultima venta cargada
    es de hace una semana), los lags saldrian mal: se calculan por POSICION de
    fila (`pandas.shift`), no por fecha real, y el hueco correspondería a una
    ventana equivocada sin que el sistema lo note.
    """
    t0 = time.perf_counter()
    history = await sales_history_service.get_history_before(db, clasificador, fecha_limite)
    recorder.record(
        PipelineStage.FETCH_HISTORY,
        PipelineEventStatus.COMPLETED,
        (time.perf_counter() - t0) * 1000,
        f"{len(history)} filas de historial real (desde BD)",
    )
    if logger.isEnabledFor(logging.DEBUG) and not history.empty:
        cola = history.tail(3)[["dia", "cantidad_vendida", "precio_medio"]]
        etiqueta = paint("   ultimos datos leidos de la BD:", "blue")
        logger.debug("%s\n%s", etiqueta, cola.to_string(index=False))

    if history.empty:
        return history

    fecha_limite_ts = pd.Timestamp(fecha_limite)
    ultimo_dia_real = history["dia"].max()
    dias_faltantes = (fecha_limite_ts - ultimo_dia_real).days - 1
    if dias_faltantes <= 0:
        return history

    relleno_inicio = ultimo_dia_real + pd.Timedelta(days=1)
    t0 = time.perf_counter()
    history = features.extend_history_with_predictions(
        registry, history, clasificador, relleno_inicio, dias_faltantes
    )
    recorder.record(
        PipelineStage.BACKFILL_GAP,
        PipelineEventStatus.COMPLETED,
        (time.perf_counter() - t0) * 1000,
        f"{dias_faltantes} dia(s) sin dato real, rellenados en cadena desde "
        f"{relleno_inicio:%Y-%m-%d}",
    )
    return history


async def predict_day(
    db: AsyncSession,
    registry: MLModelRegistry,
    settings: Settings,
    *,
    clasificador: str,
    fecha: date,
    user_id: uuid.UUID | None,
) -> tuple[int, uuid.UUID, explanation_service.ExplanationSnapshot | None]:
    """Predice un unico dia (pasado o futuro), instrumentando cada etapa del pipeline.

    Si no hay historial real contiguo justo antes de `fecha` (por ejemplo, la
    fecha pedida esta mas alla del ultimo dato real cargado), rellena el hueco
    encadenando predicciones (ver `_fetch_and_backfill_history`) antes de
    construir las features de `fecha` — es el "respaldo por pasos" transparente
    para el llamador.

    Ademas de la prediccion, genera y persiste una explicacion XAI (ver
    `app.services.explanation_service`) — esta es la UNICA funcion de
    prediccion que lo hace: `predict_range` (usada por /week, /range y
    /day-x) nunca genera explicacion, por diseño, ya que la regla de negocio
    es limitar el LLM a consultas de un dia especifico.
    """
    _validate_clasificador(registry, clasificador)
    recorder = _EventRecorder()
    fecha_ts = pd.Timestamp(fecha)
    start_total = time.perf_counter()
    _log_header(PredictionHorizon.DAY, clasificador, fecha, dias=1)

    history = await _fetch_and_backfill_history(db, registry, clasificador, fecha, recorder)

    t0 = time.perf_counter()
    fila = features.build_feature_row(
        history, clasificador, fecha_ts, registry.lags, registry.historia_minima
    )
    recorder.record(
        PipelineStage.BUILD_FEATURES,
        PipelineEventStatus.COMPLETED,
        (time.perf_counter() - t0) * 1000,
        "lags + medias moviles + calendario",
    )

    t0 = time.perf_counter()
    x = features.encode_and_align(fila, registry)
    recorder.record(
        PipelineStage.ENCODE_ALIGN,
        PipelineEventStatus.COMPLETED,
        (time.perf_counter() - t0) * 1000,
        f"one-hot(clasificador) -> {len(registry.feature_cols)} features alineadas",
    )
    if logger.isEnabledFor(logging.DEBUG):
        claves = ["lag_1", "lag_7", "lag_14", "roll_mean_7", "roll_mean_14"]
        vals = {k: round(float(x.iloc[0][k]), 2) for k in claves if k in x.columns}
        logger.debug("%s %s", paint("   features clave que entran al modelo:", "cyan"), vals)

    t0 = time.perf_counter()
    pred_log = features.predict_log_value(registry, x)
    recorder.record(
        PipelineStage.MODEL_INFERENCE,
        PipelineEventStatus.COMPLETED,
        (time.perf_counter() - t0) * 1000,
        f"XGBoost {registry.model_version} -> log={pred_log:.4f}",
    )

    t0 = time.perf_counter()
    prediction = features.postprocess_prediction(pred_log)
    recorder.record(
        PipelineStage.POSTPROCESS,
        PipelineEventStatus.COMPLETED,
        (time.perf_counter() - t0) * 1000,
        f"expm1 + recorte -> {prediction} u.",
    )

    total_duration_ms = (time.perf_counter() - start_total) * 1000

    # 1. Persistir el InferenceLog primero, solo (sin explicacion todavia).
    inference_log_id = uuid.uuid4()
    inference_log = InferenceLog(
        id=inference_log_id,
        user_id=user_id,
        clasificador=clasificador,
        fecha_objetivo=fecha,
        horizonte=PredictionHorizon.DAY,
        dias=1,
        prediction_value=float(prediction),
        duration_ms=total_duration_ms,
        model_version=registry.model_version,
    )
    inference_log.events = recorder.events
    await _persist_inference_log(db, inference_log)
    _log_footer(f"{prediction} u.", total_duration_ms, registry.model_version, inference_log_id)

    # 2. Generar y persistir la explicacion XAI en una transaccion SEPARADA
    # (ver `_persist_explanation`) — SOLO predict_day la genera (nunca
    # predict_range, usada por /week, /range y /day-x): es la regla de
    # negocio de limitar el LLM a consultas de un dia especifico. Un fallo
    # aqui (generando o persistiendo) nunca debe tumbar la respuesta de la
    # prediccion en si, ni el registro de auditoria ya confirmado arriba —
    # se degrada a "sin explicacion".
    explanation_snapshot: explanation_service.ExplanationSnapshot | None = None
    t0 = time.perf_counter()
    try:
        explanation = await explanation_service.generar_explicacion(
            db,
            settings,
            registry,
            clasificador=clasificador,
            fecha=fecha,
            prediction=prediction,
            fila_base=fila,
            x_base=x,
            history=history,
        )
        explanation_snapshot = explanation_service.to_snapshot(explanation)
        evento = PipelineEvent(
            id=uuid.uuid4(),
            stage=PipelineStage.EXPLANATION,
            status=PipelineEventStatus.COMPLETED,
            duration_ms=(time.perf_counter() - t0) * 1000,
            message=f"explicacion generada via '{explanation.generado_por}'",
        )
        await _persist_explanation(db, inference_log_id, explanation, evento)
    except Exception:
        logger.warning(
            "No se pudo generar/persistir la explicacion de la prediccion, se omite.",
            exc_info=True,
        )

    return prediction, inference_log_id, explanation_snapshot


async def predict_range(
    db: AsyncSession,
    registry: MLModelRegistry,
    settings: Settings,
    *,
    clasificador: str,
    fecha_inicio: date,
    dias: int,
    horizonte: PredictionHorizon,
    user_id: uuid.UUID | None,
    generar_explicacion: bool = False,
) -> tuple[list[tuple[date, int]], int, uuid.UUID, explanation_service.ExplanationSnapshot | None]:
    """Predice `dias` consecutivos desde `fecha_inicio` (semana, mes o "dia X").

    Si hace falta, rellena primero el hueco de calendario entre el ultimo dato
    real y `fecha_inicio` (ver `_fetch_and_backfill_history`), y despues
    encadena los `dias` pedidos. Registra un evento de pipeline por dia
    iterado, ademas del de obtencion/relleno de historial.

    `generar_explicacion=True` (solo /week y /range; NUNCA cuando esta
    funcion la llama `predict_day_x`, que ya genera su propia explicacion a
    nivel de dia) agrega una explicacion EN CONJUNTO del periodo completo --
    una sola llamada al LLM sin importar `dias`, nunca una por dia (ver
    `explanation_service.generar_explicacion_periodo`).
    """
    _validate_clasificador(registry, clasificador)
    recorder = _EventRecorder()
    fecha_inicio_ts = pd.Timestamp(fecha_inicio)
    start_total = time.perf_counter()
    _log_header(horizonte, clasificador, fecha_inicio, dias=dias)

    history = await _fetch_and_backfill_history(db, registry, clasificador, fecha_inicio, recorder)

    def _on_day(i: int, fecha: pd.Timestamp, prediccion: int, duration_ms: float) -> None:
        recorder.record(
            f"day_{i + 1}_of_{dias}",
            PipelineEventStatus.COMPLETED,
            duration_ms,
            f"{fecha:%Y-%m-%d} -> {prediccion} u.",
        )

    predicciones, total = features.predict_range(
        registry, history, clasificador, fecha_inicio_ts, dias, on_day=_on_day
    )

    total_duration_ms = (time.perf_counter() - start_total) * 1000

    inference_log_id = uuid.uuid4()
    inference_log = InferenceLog(
        id=inference_log_id,
        user_id=user_id,
        clasificador=clasificador,
        fecha_objetivo=fecha_inicio,
        horizonte=horizonte,
        dias=dias,
        prediction_value=float(total),
        duration_ms=total_duration_ms,
        model_version=registry.model_version,
    )
    inference_log.events = recorder.events
    await _persist_inference_log(db, inference_log)
    _log_footer(
        f"{total} u. en {dias} dias", total_duration_ms, registry.model_version, inference_log_id
    )

    predicciones_date: list[tuple[date, int]] = [(ts.date(), pred) for ts, pred in predicciones]

    explanation_snapshot: explanation_service.ExplanationSnapshot | None = None
    if generar_explicacion:
        t0 = time.perf_counter()
        try:
            explanation = await explanation_service.generar_explicacion_periodo(
                db,
                settings,
                clasificador=clasificador,
                fecha_inicio=predicciones_date[0][0],
                fecha_fin=predicciones_date[-1][0],
                dias=dias,
                total=total,
                predicciones_diarias=predicciones_date,
                history=history,
            )
            explanation_snapshot = explanation_service.to_snapshot(explanation)
            evento = PipelineEvent(
                id=uuid.uuid4(),
                stage=PipelineStage.EXPLANATION,
                status=PipelineEventStatus.COMPLETED,
                duration_ms=(time.perf_counter() - t0) * 1000,
                message=f"explicacion de periodo generada via '{explanation.generado_por}'",
            )
            await _persist_explanation(db, inference_log_id, explanation, evento)
        except Exception:
            logger.warning(
                "No se pudo generar/persistir la explicacion del periodo, se omite.",
                exc_info=True,
            )

    return predicciones_date, total, inference_log_id, explanation_snapshot


async def predict_day_x(
    db: AsyncSession,
    registry: MLModelRegistry,
    settings: Settings,
    *,
    clasificador: str,
    fecha_objetivo: date,
    user_id: uuid.UUID | None,
) -> tuple[
    int, int, list[tuple[date, int]], date, uuid.UUID, explanation_service.ExplanationSnapshot | None
]:
    """Predice un dia objetivo concreto, encadenando "desde hoy" cuando hace falta.

    Retorna `(prediccion_individual, prediccion_acumulada, predicciones_diarias,
    fecha_inicio, inference_log_id, explicacion)`:
    - `prediccion_individual`: cuanto se vende SOLO en `fecha_objetivo`.
    - `prediccion_acumulada`: la suma de todo el periodo desde `fecha_inicio`
      (hoy, si `fecha_objetivo` es futura; o la propia `fecha_objetivo`, si ya
      paso o es hoy) hasta `fecha_objetivo`.

    Reutiliza `predict_range` tal cual (mismo encadenado, mismos eventos de
    pipeline, misma persistencia de `inference_log`) — solo decide el punto de
    partida y separa el ultimo valor de la cadena como resultado individual.

    Tambien genera una explicacion XAI para `fecha_objetivo`, igual que
    `predict_day`: desde la perspectiva de quien consulta, "Dia X" ES la
    funcionalidad de predecir un dia especifico (que el backend internamente
    tenga que encadenar varios dias para llegar ahi es un detalle de
    implementacion). Recalcula la fila de features de `fecha_objetivo` una
    vez mas -- `predict_range` no expone la fila del ultimo dia -- lo cual
    cuesta una consulta a BD y una inferencia XGBoost adicionales (sub-100ms),
    aceptable para un endpoint de consulta puntual como este.
    """
    _validate_clasificador(registry, clasificador)

    hoy = date.today()
    fecha_inicio = fecha_objetivo if fecha_objetivo <= hoy else hoy
    dias = (fecha_objetivo - fecha_inicio).days + 1

    if dias > MAX_DIAS_DAY_X:
        raise DateTooFarError(
            f"La fecha objetivo esta a {dias} dias desde {fecha_inicio:%Y-%m-%d}; "
            f"el maximo soportado es {MAX_DIAS_DAY_X} dias."
        )

    # `generar_explicacion` se deja en False (default): day-x ya genera su
    # propia explicacion a nivel de dia mas abajo -- una de periodo aqui
    # seria redundante.
    predicciones, total, inference_log_id, _ = await predict_range(
        db,
        registry,
        settings,
        clasificador=clasificador,
        fecha_inicio=fecha_inicio,
        dias=dias,
        horizonte=PredictionHorizon.DAY_X,
        user_id=user_id,
    )

    prediccion_individual = predicciones[-1][1]

    # Igual que en `predict_day`: la explicacion se genera y persiste en una
    # transaccion SEPARADA del `InferenceLog` de arriba (ya confirmado por
    # `predict_range`). Un fallo aqui (generando o persistiendo, p.ej. porque
    # `prediction_explanations` no existe todavia) nunca debe perder ni
    # invalidar el registro de la prediccion ya guardado -- ver
    # `_persist_explanation`.
    explanation_snapshot: explanation_service.ExplanationSnapshot | None = None
    t0 = time.perf_counter()
    try:
        recorder = _EventRecorder()
        history = await _fetch_and_backfill_history(db, registry, clasificador, fecha_objetivo, recorder)
        fila = features.build_feature_row(
            history, clasificador, pd.Timestamp(fecha_objetivo), registry.lags, registry.historia_minima
        )
        x = features.encode_and_align(fila, registry)
        explanation = await explanation_service.generar_explicacion(
            db,
            settings,
            registry,
            clasificador=clasificador,
            fecha=fecha_objetivo,
            prediction=prediccion_individual,
            fila_base=fila,
            x_base=x,
            history=history,
        )
        explanation_snapshot = explanation_service.to_snapshot(explanation)
        evento = PipelineEvent(
            id=uuid.uuid4(),
            stage=PipelineStage.EXPLANATION,
            status=PipelineEventStatus.COMPLETED,
            duration_ms=(time.perf_counter() - t0) * 1000,
            message=f"explicacion generada via '{explanation.generado_por}'",
        )
        await _persist_explanation(db, inference_log_id, explanation, evento)
    except Exception:
        logger.warning(
            "No se pudo generar/persistir la explicacion de la prediccion day-x, se omite.",
            exc_info=True,
        )

    return prediccion_individual, total, predicciones, fecha_inicio, inference_log_id, explanation_snapshot


async def list_prediction_history(
    db: AsyncSession,
    *,
    clasificador: str | None,
    from_date: date | None,
    to_date: date | None,
    page: int,
    page_size: int,
) -> tuple[list[InferenceLog], int]:
    """Historial paginado de TODAS las predicciones con explicacion --
    DAY/DAY_X (por dia) y tambien WEEK/RANGE (en conjunto, por periodo) --
    mas recientes primero, con su explicacion precargada.

    A diferencia de `/logs/inferences` (solo admins, auditoria tecnica), esta
    consulta esta pensada para el modulo de historial del propio usuario: no
    filtra por `user_id` porque el catalogo de categorias es compartido por
    todo el equipo de la tienda, no privado por persona. No filtra por
    horizonte: desde que /week y /range tambien generan explicacion, no hay
    motivo para esconderlas aqui.
    """
    filters: list[ColumnElement[bool]] = []
    if clasificador is not None:
        filters.append(InferenceLog.clasificador == clasificador)
    if from_date is not None:
        filters.append(InferenceLog.fecha_objetivo >= from_date)
    if to_date is not None:
        filters.append(InferenceLog.fecha_objetivo <= to_date)

    total = (
        await db.execute(select(func.count()).select_from(InferenceLog).where(*filters))
    ).scalar_one()

    stmt = (
        select(InferenceLog)
        .options(selectinload(InferenceLog.explanation))
        .where(*filters)
        .order_by(InferenceLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows), total


async def get_prediction_detail(db: AsyncSession, inference_log_id: uuid.UUID) -> InferenceLog | None:
    """Una prediccion por id (cualquier horizonte), con su explicacion
    precargada si existe."""
    stmt = (
        select(InferenceLog)
        .options(selectinload(InferenceLog.explanation))
        .where(InferenceLog.id == inference_log_id)
    )
    return (await db.execute(stmt)).scalar_one_or_none()
