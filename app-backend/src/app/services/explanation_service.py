"""Genera la explicacion XAI de una prediccion de un unico dia (/predictions/day).

Todo el calculo numerico (factores por perturbacion, dia historico similar,
margen de error reciente) ocurre ANTES de llamar al LLM y es 100%
determinista y verificable contra la base de datos; el LLM (OpenAI, mismo
proveedor y patron de fallback que `app.reports.summary_llm`) solo tiene el
trabajo de REDACTAR esos hechos ya calculados en lenguaje natural para un
cliente sin conocimientos tecnicos -- nunca de "adivinar" el porque a partir
de features crudas, que es donde una explicacion se vuelve generica o
inventada. Los `factores` que ve el cliente son SIEMPRE los calculados en
Python (ver `app.ml.explainability`), esten o no disponibles el LLM: el LLM
nunca reescribe esas cifras.

Si no hay `OPENAI_API_KEY`, la llamada tarda mas de
`settings.llm_explanation_timeout_seconds`, o falla por cualquier motivo, se
degrada a una redaccion por plantilla con los mismos datos ya calculados: la
respuesta de /predictions/day nunca se bloquea por el LLM.
"""

import asyncio
import json
import logging
import time
from datetime import date, timedelta
from typing import Any, Literal, TypedDict

import pandas as pd
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import PredictionHorizon
from app.db.models.inference_log import InferenceLog
from app.db.models.inventory_stock import InventoryStock
from app.db.models.prediction_explanation import PredictionExplanation
from app.db.models.sales_history import SalesHistory
from app.ml import explainability
from app.ml.registry import MLModelRegistry

logger = logging.getLogger("app.ml.explanation")

_SYSTEM_PROMPT = (
    "Eres un asistente que traduce predicciones de un modelo de Machine Learning a "
    "explicaciones claras para un cliente sin conocimientos tecnicos de una tienda de "
    "productos para mascotas.\n\n"
    "Reglas:\n"
    "- No inventes cifras que no esten en los datos que te paso.\n"
    "- No menciones terminos tecnicos (modelo, feature, lag, SHAP, algoritmo, dataset, "
    "perturbacion, XGBoost, contribucion).\n"
    "- Explica el 'por que' apoyandote en los hechos que te doy (tendencia reciente, dia "
    "de la semana, dia parecido en el pasado, promedio historico de ese dia de la semana), "
    "sin agregar factores nuevos.\n"
    "- Si te paso el stock fisico actual, menciona en la recomendacion si alcanza o no para "
    "la demanda esperada -- solo si el dato viene en los hechos, nunca lo inventes.\n"
    "- Tono cercano y profesional, nunca alarmista ni exagerado. Maximo 3 frases.\n"
    "- Responde SOLO el JSON solicitado, sin texto adicional ni markdown."
)


def _factor_descripcion(nombre: str, delta: int) -> str:
    label = explainability.FEATURE_LABELS.get(nombre, nombre)
    if delta >= 0:
        return f"{label} empuja la predicción {abs(delta)} unidad(es) hacia arriba."
    return f"{label} empuja la predicción {abs(delta)} unidad(es) hacia abajo."


def _factores_a_dict(factores_calc: list[tuple[str, int]]) -> list[dict[str, object]]:
    """Convierte los `(nombre_variable, delta)` calculados por perturbacion al
    shape de `app.schemas.prediction.ExplanationFactor`. Es la UNICA fuente de
    los factores mostrados al cliente -- ni el LLM ni el fallback los recalculan."""
    return [
        {
            "factor": explainability.FEATURE_LABELS.get(nombre, nombre),
            "impacto_unidades": delta,
            "direccion": "sube" if delta >= 0 else "baja",
            "descripcion": _factor_descripcion(nombre, delta),
        }
        for nombre, delta in factores_calc
    ]


async def calcular_margen_error_reciente(
    db: AsyncSession, clasificador: str, *, dias_ventana: int = 30, minimo_muestras: int = 3
) -> float | None:
    """MAE de las predicciones de horizonte `day` ya vencidas (`fecha_objetivo`
    en el pasado) de los ultimos `dias_ventana` dias, cruzando `inference_logs`
    con la venta real registrada en `sales_history` para esa misma fecha y
    clasificador.

    Retorna `None` si no hay al menos `minimo_muestras` predicciones vencidas
    todavia (caso normal en un sistema recien desplegado) -- mostrar un
    margen de error calculado sobre 1-2 muestras seria mas ruido que senal.
    """
    hoy = date.today()
    desde = hoy - timedelta(days=dias_ventana)
    stmt = select(InferenceLog.prediction_value, SalesHistory.cantidad_vendida).join(
        SalesHistory,
        (SalesHistory.clasificador == InferenceLog.clasificador)
        & (SalesHistory.dia == InferenceLog.fecha_objetivo),
    ).where(
        InferenceLog.clasificador == clasificador,
        InferenceLog.horizonte == PredictionHorizon.DAY,
        InferenceLog.fecha_objetivo < hoy,
        InferenceLog.fecha_objetivo >= desde,
    )
    rows = (await db.execute(stmt)).all()
    if len(rows) < minimo_muestras:
        return None
    errores = [abs(pred - real) for pred, real in rows]
    return round(sum(errores) / len(errores), 1)


def _fallback_narrar(
    fecha: date,
    prediction: int,
    ancla: int,
    dia_similar: tuple[pd.Timestamp, int] | None,
    margen_error: float | None,
    promedio_dia_semana: float | None,
    stock_actual: float | None,
) -> tuple[str, str | None]:
    """Redaccion sin LLM: frases deterministas sobre los mismos datos ya
    calculados, siempre disponible (ver `app.reports.summary_llm` para el
    mismo patron aplicado a los reportes)."""
    diff = prediction - ancla
    if ancla > 0 and diff != 0:
        variacion = round(abs(diff) / ancla * 100)
        tendencia = f"un {variacion}% mas de lo habitual" if diff > 0 else f"un {variacion}% menos de lo habitual"
    else:
        tendencia = "en linea con lo habitual"

    resumen = f"Para el {fecha:%d/%m/%Y} se esperan {prediction} unidades en esta categoria, {tendencia}."
    if dia_similar is not None:
        fecha_similar, cantidad_similar = dia_similar
        resumen += (
            f" Se parece a lo ocurrido el {fecha_similar:%d/%m/%Y}, cuando se "
            f"vendieron {cantidad_similar} unidades."
        )
    if promedio_dia_semana is not None:
        resumen += (
            f" Este dia de la semana suele vender {promedio_dia_semana:g} unidades en promedio."
        )

    partes_recomendacion = []
    if margen_error is not None:
        partes_recomendacion.append(
            f"El sistema suele acertar esta categoria con un margen de +/-{margen_error:g} unidades."
        )
    if stock_actual is not None and stock_actual < prediction:
        partes_recomendacion.append(
            f"El stock actual ({stock_actual:g} u.) esta por debajo de la demanda esperada."
        )
    recomendacion = " ".join(partes_recomendacion) if partes_recomendacion else None
    return resumen, recomendacion


async def _llm_narrar(
    settings: Settings,
    *,
    clasificador: str,
    fecha: date,
    prediction: int,
    ancla: int,
    factores_calc: list[tuple[str, int]],
    dia_similar: tuple[pd.Timestamp, int] | None,
    margen_error: float | None,
    promedio_dia_semana: float | None,
    stock_actual: float | None,
) -> tuple[str, str | None]:
    """Llama al LLM SOLO para redactar `(resumen, recomendacion)` a partir de
    hechos ya calculados; nunca decide los numeros de `factores`."""
    lineas = [
        f"Categoria: {clasificador}",
        f"Fecha: {fecha:%A %d de %B de %Y}",
        f"Prediccion final: {prediction} unidades",
        f"Punto de referencia (promedio reciente de esta categoria): {ancla} unidades",
    ]
    if factores_calc:
        lineas.append("Factores verificados que explican la diferencia (no agregues otros):")
        lineas.extend(f"- {_factor_descripcion(nombre, delta)}" for nombre, delta in factores_calc)
    if dia_similar is not None:
        fecha_similar, cantidad_similar = dia_similar
        lineas.append(
            f"Dia historico mas parecido: {fecha_similar:%d/%m/%Y}, se vendieron "
            f"{cantidad_similar} unidades."
        )
    if margen_error is not None:
        lineas.append(
            f"Margen de error habitual del sistema en esta categoria: +/-{margen_error:g} unidades."
        )
    if promedio_dia_semana is not None:
        lineas.append(
            f"Promedio historico de ese mismo dia de la semana ({fecha:%A}): "
            f"{promedio_dia_semana:g} unidades."
        )
    if stock_actual is not None:
        lineas.append(f"Stock fisico actual disponible de esta categoria: {stock_actual:g} unidades.")
    lineas.append(
        '\nDevuelve JSON con esta forma exacta: {"resumen": "...", "recomendacion": "..." o null}'
    )

    # `async with` cierra el cliente (y su pool de conexiones httpx) al salir.
    # Sin esto, cada llamada deja un `AsyncOpenAI` sin cerrar -- en un proceso
    # de larga duracion que acumula muchas llamadas, las conexiones a medio
    # cerrar terminan agotando el pool y las siguientes llamadas fallan con
    # errores de conexion (`httpcore.ConnectError`), sin relacion con el
    # request en si.
    async with AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value()) as client:  # type: ignore[union-attr]
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": "\n".join(lineas)},
            ],
            temperature=0.3,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
    content = response.choices[0].message.content
    if not content or not content.strip():
        raise ValueError("Respuesta vacia del LLM.")

    data = json.loads(content)
    resumen = str(data.get("resumen", "")).strip()
    if not resumen:
        raise ValueError("El LLM no devolvio un resumen.")
    recomendacion = data.get("recomendacion")
    return resumen, (str(recomendacion).strip() if recomendacion else None)


def _promedio_mismo_dia_semana(
    history: pd.DataFrame, fecha: date, *, minimo_muestras: int = 3
) -> float | None:
    """Promedio historico de ventas en el MISMO dia de la semana que `fecha`
    (ej. el promedio de todos los miercoles anteriores), calculado sobre el
    `history` ya cargado -- sin consultas adicionales a la base de datos.

    Retorna `None` si hay menos de `minimo_muestras` observaciones de ese dia
    de la semana todavia (dato poco fiable con 1-2 muestras)."""
    if history.empty:
        return None
    misma_dow = history[history["dia"].dt.dayofweek == fecha.weekday()]
    if len(misma_dow) < minimo_muestras:
        return None
    return round(float(misma_dow["cantidad_vendida"].mean()), 1)


async def obtener_stock_actual(db: AsyncSession, clasificador: str) -> float | None:
    """Stock fisico actual de la categoria (independiente del modelo de
    forecasting), para comparar contra la demanda predicha. `None` si la
    categoria no tiene stock cargado todavia (`inventory_stock` vacio para
    ese clasificador) -- caso normal si nadie ha usado /inventory todavia."""
    stmt = select(InventoryStock.stock_actual).where(InventoryStock.clasificador == clasificador)
    return (await db.execute(stmt)).scalar_one_or_none()


def _historial_reciente(history: pd.DataFrame, dias: int = 14) -> list[dict[str, object]]:
    """Ultimos `dias` de historial (real o real+relleno) antes del dia
    explicado, en el shape que el frontend usa para dibujar un grafico de
    tendencia simple junto al texto -- la version "grafica" de la
    explicacion, no solo prosa."""
    if history.empty:
        return []
    cola = history.sort_values("dia").tail(dias)
    return [
        {"fecha": fecha.strftime("%Y-%m-%d"), "cantidad": int(cantidad)}
        for fecha, cantidad in zip(cola["dia"], cola["cantidad_vendida"], strict=True)
    ]


async def generar_explicacion(
    db: AsyncSession,
    settings: Settings,
    registry: MLModelRegistry,
    *,
    clasificador: str,
    fecha: date,
    prediction: int,
    fila_base: pd.DataFrame,
    x_base: pd.DataFrame,
    history: pd.DataFrame,
) -> PredictionExplanation:
    """Orquesta el calculo XAI completo para una prediccion de un unico dia y
    retorna el `PredictionExplanation` (ORM, todavia sin asociar/persistir).

    El calculo numerico ocurre siempre, haya o no LLM disponible. Solo la
    redaccion del resumen/recomendacion depende del LLM, con fallback a
    plantilla ante cualquier fallo -- nunca bloquea la respuesta al cliente.
    """
    t0 = time.perf_counter()

    variables_relevantes = explainability.rank_contribuciones(registry, x_base)
    factores_calc = explainability.explicar_por_perturbacion(
        registry, fila_base, prediction, variables_relevantes
    )
    ancla = int(round(fila_base["roll_mean_7"].iloc[0])) if "roll_mean_7" in fila_base else prediction
    dow = int(fila_base["dow"].iloc[0])
    lag_1 = float(fila_base["lag_1"].iloc[0])
    lag_7 = float(fila_base["lag_7"].iloc[0])
    dia_similar = explainability.dia_similar_mas_cercano(history, dow, lag_1, lag_7)
    margen_error = await calcular_margen_error_reciente(db, clasificador)
    promedio_dia_semana = _promedio_mismo_dia_semana(history, fecha)
    stock_actual = await obtener_stock_actual(db, clasificador)

    if settings.openai_api_key is None:
        resumen, recomendacion = _fallback_narrar(
            fecha, prediction, ancla, dia_similar, margen_error, promedio_dia_semana, stock_actual
        )
        generado_por = "fallback"
        modelo_llm = None
    else:
        try:
            resumen, recomendacion = await asyncio.wait_for(
                _llm_narrar(
                    settings,
                    clasificador=clasificador,
                    fecha=fecha,
                    prediction=prediction,
                    ancla=ancla,
                    factores_calc=factores_calc,
                    dia_similar=dia_similar,
                    margen_error=margen_error,
                    promedio_dia_semana=promedio_dia_semana,
                    stock_actual=stock_actual,
                ),
                timeout=settings.llm_explanation_timeout_seconds,
            )
            generado_por = "llm"
            modelo_llm = settings.openai_model
        except Exception:
            logger.warning(
                "Fallo la generacion de la explicacion con OpenAI, usando fallback.", exc_info=True
            )
            resumen, recomendacion = _fallback_narrar(
                fecha, prediction, ancla, dia_similar, margen_error, promedio_dia_semana, stock_actual
            )
            generado_por = "fallback"
            modelo_llm = None

    logger.info(
        "Explicacion (%s) generada en %.1f ms para %s %s",
        generado_por,
        (time.perf_counter() - t0) * 1000,
        clasificador,
        fecha,
    )

    return PredictionExplanation(
        fecha=fecha,
        prediccion=prediction,
        resumen=resumen,
        factores=_factores_a_dict(factores_calc),
        recomendacion=recomendacion,
        dia_similar_fecha=dia_similar[0].date() if dia_similar else None,
        dia_similar_cantidad=dia_similar[1] if dia_similar else None,
        margen_error_habitual=margen_error,
        promedio_dia_semana=promedio_dia_semana,
        stock_actual=stock_actual,
        generado_por=generado_por,
        modelo_llm=modelo_llm,
        historial_reciente=_historial_reciente(history),
    )


def _fallback_narrar_periodo(
    fecha_inicio: date,
    fecha_fin: date,
    total: int,
    promedio: int,
    pico: tuple[date, int],
    periodo_anterior_total: int | None,
    stock_actual: float | None,
) -> tuple[str, str | None]:
    resumen = (
        f"Del {fecha_inicio:%d/%m} al {fecha_fin:%d/%m} se esperan {total} unidades en total "
        f"({promedio} por dia en promedio). El dia con mas demanda es el {pico[0]:%d/%m}, con "
        f"{pico[1]} unidades."
    )
    if periodo_anterior_total is not None and periodo_anterior_total > 0:
        diff = round((total - periodo_anterior_total) / periodo_anterior_total * 100)
        if diff > 0:
            resumen += f" Esto es un {diff}% mas que el periodo equivalente anterior."
        elif diff < 0:
            resumen += f" Esto es un {abs(diff)}% menos que el periodo equivalente anterior."
        else:
            resumen += " Es un nivel similar al periodo equivalente anterior."

    recomendacion = None
    if stock_actual is not None and stock_actual < total:
        recomendacion = (
            f"El stock actual ({stock_actual:g} u.) esta por debajo de la demanda esperada "
            "para todo el periodo."
        )
    return resumen, recomendacion


async def _llm_narrar_periodo(
    settings: Settings,
    *,
    clasificador: str,
    fecha_inicio: date,
    fecha_fin: date,
    total: int,
    promedio: int,
    pico: tuple[date, int],
    valle: tuple[date, int],
    periodo_anterior_total: int | None,
    stock_actual: float | None,
) -> tuple[str, str | None]:
    """Llama al LLM SOLO para redactar `(resumen, recomendacion)` de un
    PERIODO completo (nunca dia a dia) -- una unica llamada por /week o
    /range, sin importar cuantos dias tenga el periodo."""
    lineas = [
        f"Categoria: {clasificador}",
        f"Periodo: {fecha_inicio:%d de %B} al {fecha_fin:%d de %B de %Y}",
        f"Total del periodo: {total} unidades ({promedio} por dia en promedio)",
        f"Dia de mayor demanda: {pico[0]:%d/%m}, {pico[1]} unidades",
        f"Dia de menor demanda: {valle[0]:%d/%m}, {valle[1]} unidades",
    ]
    if periodo_anterior_total is not None:
        dias_periodo = (fecha_fin - fecha_inicio).days + 1
        lineas.append(
            f"Total de los {dias_periodo} dias INMEDIATAMENTE ANTERIORES a esta fecha de inicio "
            f"(NO del año pasado, son los dias justo antes en este mismo calendario): "
            f"{periodo_anterior_total} unidades"
        )
    if stock_actual is not None:
        lineas.append(
            f"Stock fisico actual disponible de esta categoria: {stock_actual:g} unidades "
            "(para cubrir todo el periodo)."
        )
    lineas.append(
        '\nDevuelve JSON con esta forma exacta: {"resumen": "...", "recomendacion": "..." o null}. '
        "Si mencionas la comparacion con el periodo anterior, dila como 'el periodo anterior' o "
        "'la semana/mes pasado', nunca como 'el año anterior' ni inventes una fecha para esa comparacion."
    )

    async with AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value()) as client:  # type: ignore[union-attr]
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": "\n".join(lineas)},
            ],
            temperature=0.3,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
    content = response.choices[0].message.content
    if not content or not content.strip():
        raise ValueError("Respuesta vacia del LLM.")

    data = json.loads(content)
    resumen = str(data.get("resumen", "")).strip()
    if not resumen:
        raise ValueError("El LLM no devolvio un resumen.")
    recomendacion = data.get("recomendacion")
    return resumen, (str(recomendacion).strip() if recomendacion else None)


async def generar_explicacion_periodo(
    db: AsyncSession,
    settings: Settings,
    *,
    clasificador: str,
    fecha_inicio: date,
    fecha_fin: date,
    dias: int,
    total: int,
    predicciones_diarias: list[tuple[date, int]],
    history: pd.DataFrame,
) -> PredictionExplanation:
    """Explicacion EN CONJUNTO de un periodo completo (/week, /range) -- nunca
    dia por dia: una unica llamada al LLM (o fallback) sin importar cuantos
    dias tenga el periodo, con datos generales (total, promedio, pico, valle,
    comparacion con el periodo anterior, stock actual) en vez del desglose
    por-dia que usa `generar_explicacion` para /day y /day-x.
    """
    t0 = time.perf_counter()

    promedio = round(total / dias) if dias else 0
    pico = max(predicciones_diarias, key=lambda t: t[1])
    valle = min(predicciones_diarias, key=lambda t: t[1])

    periodo_anterior_total: int | None = None
    if not history.empty:
        h = history.sort_values("dia")
        ventana = h[h["dia"] < pd.Timestamp(fecha_inicio)].tail(dias)
        if len(ventana) == dias:
            periodo_anterior_total = int(ventana["cantidad_vendida"].sum())

    stock_actual = await obtener_stock_actual(db, clasificador)

    if settings.openai_api_key is None:
        resumen, recomendacion = _fallback_narrar_periodo(
            fecha_inicio, fecha_fin, total, promedio, pico, periodo_anterior_total, stock_actual
        )
        generado_por = "fallback"
        modelo_llm = None
    else:
        try:
            resumen, recomendacion = await asyncio.wait_for(
                _llm_narrar_periodo(
                    settings,
                    clasificador=clasificador,
                    fecha_inicio=fecha_inicio,
                    fecha_fin=fecha_fin,
                    total=total,
                    promedio=promedio,
                    pico=pico,
                    valle=valle,
                    periodo_anterior_total=periodo_anterior_total,
                    stock_actual=stock_actual,
                ),
                timeout=settings.llm_explanation_timeout_seconds,
            )
            generado_por = "llm"
            modelo_llm = settings.openai_model
        except Exception:
            logger.warning(
                "Fallo la generacion de la explicacion de periodo con OpenAI, usando fallback.",
                exc_info=True,
            )
            resumen, recomendacion = _fallback_narrar_periodo(
                fecha_inicio, fecha_fin, total, promedio, pico, periodo_anterior_total, stock_actual
            )
            generado_por = "fallback"
            modelo_llm = None

    logger.info(
        "Explicacion de periodo (%s) generada en %.1f ms para %s %s..%s",
        generado_por,
        (time.perf_counter() - t0) * 1000,
        clasificador,
        fecha_inicio,
        fecha_fin,
    )

    return PredictionExplanation(
        fecha=fecha_inicio,
        prediccion=total,
        resumen=resumen,
        factores=[],
        recomendacion=recomendacion,
        dia_similar_fecha=None,
        dia_similar_cantidad=None,
        margen_error_habitual=None,
        promedio_dia_semana=None,
        stock_actual=stock_actual,
        generado_por=generado_por,
        modelo_llm=modelo_llm,
        historial_reciente=_historial_reciente(history),
    )


class ExplanationSnapshot(TypedDict):
    """Copia plana e inmutable de un `PredictionExplanation`, desacoplada de la
    sesion de SQLAlchemy -- ver `to_snapshot`."""

    fecha: date
    prediccion: int
    resumen: str
    factores: list[dict[str, Any]]
    dia_similar_fecha: date | None
    dia_similar_cantidad: int | None
    margen_error_habitual: float | None
    promedio_dia_semana: float | None
    stock_actual: float | None
    recomendacion: str | None
    generado_por: Literal["llm", "fallback"]
    historial_reciente: list[dict[str, Any]]


def to_snapshot(explanation: PredictionExplanation) -> ExplanationSnapshot:
    """Copia los campos del ORM a un dict plano, desacoplado de la sesion.

    Necesario porque `AsyncSession` expira los atributos de TODOS los objetos
    (incluida `explanation`, cascada desde `InferenceLog`) al hacer `commit()`
    (`expire_on_commit=True` por defecto); leerlos despues, fuera de un
    `await`, dispara `sqlalchemy.exc.MissingGreenlet`. Llamar a esto ANTES de
    persistir evita tener que volver a tocar el objeto ORM despues.
    """
    return ExplanationSnapshot(
        fecha=explanation.fecha,
        prediccion=explanation.prediccion,
        resumen=explanation.resumen,
        factores=explanation.factores,
        dia_similar_fecha=explanation.dia_similar_fecha,
        dia_similar_cantidad=explanation.dia_similar_cantidad,
        margen_error_habitual=explanation.margen_error_habitual,
        promedio_dia_semana=explanation.promedio_dia_semana,
        stock_actual=explanation.stock_actual,
        recomendacion=explanation.recomendacion,
        generado_por=explanation.generado_por,  # type: ignore[typeddict-item]
        historial_reciente=explanation.historial_reciente,
    )
