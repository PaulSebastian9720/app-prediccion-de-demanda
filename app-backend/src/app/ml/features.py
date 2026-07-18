"""Puerto fiel del pipeline de features e inferencia de `notebooks/03_prediccion.ipynb`.

Funciones puras (sin I/O): reciben el historial ya cargado en memoria (un
`DataFrame` con columnas `clasificador, dia, cantidad_vendida, precio_medio`)
y devuelven predicciones. La consulta a la base de datos vive en
`app.services.sales_history_service`; la orquestacion e instrumentacion por
etapa (para `pipeline_events`) vive en `app.services.prediction_service`.
"""

import time
from collections.abc import Callable

import numpy as np
import pandas as pd

from app.core.exceptions import InsufficientHistoryError
from app.ml.registry import MLModelRegistry

# Callback invocado por `predict_range` tras cada dia predicho, con
# (indice_dia, fecha, cantidad_predicha, duracion_ms) - usado por el servicio
# para registrar un `pipeline_event` granular por dia sin duplicar el bucle.
OnDayCallback = Callable[[int, pd.Timestamp, int, float], None]


def build_group_features(group: pd.DataFrame, lags: list[int]) -> pd.DataFrame:
    """Calcula lags, medias/estadisticos moviles y features de calendario."""
    g = group.sort_values("dia").reset_index(drop=True)
    y = g["cantidad_vendida"]

    for lag in lags:
        g[f"lag_{lag}"] = y.shift(lag)

    pasado = y.shift(1)
    g["roll_mean_7"] = pasado.rolling(7).mean()
    g["roll_mean_14"] = pasado.rolling(14).mean()
    g["roll_std_7"] = pasado.rolling(7).std()
    g["roll_max_7"] = pasado.rolling(7).max()
    g["roll_min_7"] = pasado.rolling(7).min()
    g["expand_mean_clasificador"] = pasado.expanding().mean()

    g["diff_semana"] = g["lag_1"] - g["lag_7"]
    g["ratio_vs_media"] = g["lag_1"] / (g["roll_mean_7"] + 1)

    semana_iso = g["dia"].dt.isocalendar().week
    g["acum_semana"] = pasado.groupby(semana_iso).cumsum()

    g["dow"] = g["dia"].dt.dayofweek
    g["mes"] = g["dia"].dt.month
    g["semana"] = g["dia"].dt.isocalendar().week.astype(int)
    g["dow_sin"] = np.sin(2 * np.pi * g["dow"] / 7)
    g["dow_cos"] = np.cos(2 * np.pi * g["dow"] / 7)
    g["mes_sin"] = np.sin(2 * np.pi * g["mes"] / 12)
    g["mes_cos"] = np.cos(2 * np.pi * g["mes"] / 12)
    g["es_fin_de_semana"] = g["dow"].isin([5, 6]).astype(int)
    g["es_lunes"] = (g["dow"] == 0).astype(int)
    g["es_viernes"] = (g["dow"] == 4).astype(int)
    return g


def _append_placeholder(
    history_before: pd.DataFrame, clasificador: str, fecha: pd.Timestamp, precio_medio: float
) -> pd.DataFrame:
    placeholder = pd.DataFrame(
        {
            "clasificador": [clasificador],
            "dia": [fecha],
            "cantidad_vendida": [np.nan],
            "precio_medio": [precio_medio],
        }
    )
    return pd.concat([history_before, placeholder], ignore_index=True)


def resolve_precio_medio(
    history_before: pd.DataFrame, clasificador: str, fecha: pd.Timestamp
) -> float:
    """Ultimo `precio_medio` conocido antes de `fecha` (comportamiento de `_historial_hasta`)."""
    if history_before.empty:
        raise InsufficientHistoryError(
            f"No hay historial previo para {clasificador} antes de {fecha:%Y-%m-%d}."
        )
    return float(history_before["precio_medio"].iloc[-1])


def build_feature_row(
    history_before: pd.DataFrame,
    clasificador: str,
    fecha_objetivo: pd.Timestamp,
    lags: list[int],
    historia_minima: int,
    precio_medio: float | None = None,
) -> pd.DataFrame:
    """Construye la fila de features (sin codificar) para `fecha_objetivo`.

    `history_before` debe contener solo datos estrictamente anteriores a
    `fecha_objetivo`; esta funcion agrega la fila placeholder internamente.
    """
    if precio_medio is None:
        precio_medio = resolve_precio_medio(history_before, clasificador, fecha_objetivo)

    historial = _append_placeholder(history_before, clasificador, fecha_objetivo, precio_medio)
    con_features = build_group_features(historial, lags)
    fila = con_features[con_features["dia"] == fecha_objetivo].copy()

    if fila.empty:
        raise InsufficientHistoryError(
            f"La fecha {fecha_objetivo:%Y-%m-%d} no quedo incluida en el historial construido."
        )
    if fila[f"lag_{historia_minima}"].isna().any():
        raise InsufficientHistoryError(
            f"Historial insuficiente ({historia_minima} dias) para {clasificador} "
            f"en {fecha_objetivo:%Y-%m-%d}."
        )
    return fila


def encode_and_align(fila: pd.DataFrame, registry: MLModelRegistry) -> pd.DataFrame:
    """Aplica el `OneHotEncoder` de `clasificador` y reindexa a `feature_cols` (38 columnas)."""
    enc = registry.transformer.transform(fila[["clasificador"]])
    cols_enc = registry.transformer.get_feature_names_out(["clasificador"])
    fila_enc = pd.DataFrame(enc, columns=cols_enc, index=fila.index)
    fila_completa = pd.concat([fila, fila_enc], axis=1)
    return fila_completa[registry.feature_cols]


def predict_log_value(registry: MLModelRegistry, x: pd.DataFrame) -> float:
    """Ejecuta `model.predict` sobre la fila alineada; retorna la prediccion en escala log."""
    return registry.predict_raw(x)


def postprocess_prediction(pred_log: float) -> int:
    """Invierte `log1p` (target de entrenamiento) y recorta a unidades no negativas."""
    return max(0, round(float(np.expm1(pred_log))))


def predict_single_day(
    registry: MLModelRegistry,
    history_before: pd.DataFrame,
    clasificador: str,
    fecha_objetivo: pd.Timestamp,
    precio_medio: float | None = None,
) -> int:
    """Predice unidades vendidas para un unico dia (pasado o futuro).

    Combina las 4 etapas (build_features, encode_align, model_inference,
    postprocess) en una sola llamada; usado internamente por `predict_range`
    y en tests unitarios contra los valores de referencia del notebook.
    """
    fila = build_feature_row(
        history_before,
        clasificador,
        fecha_objetivo,
        registry.lags,
        registry.historia_minima,
        precio_medio=precio_medio,
    )
    x = encode_and_align(fila, registry)
    pred_log = predict_log_value(registry, x)
    return postprocess_prediction(pred_log)


def extend_history_with_predictions(
    registry: MLModelRegistry,
    history_before: pd.DataFrame,
    clasificador: str,
    fecha_inicio: pd.Timestamp,
    dias: int,
    on_day: OnDayCallback | None = None,
) -> pd.DataFrame:
    """Encadena `dias` predicciones desde `fecha_inicio`, retroalimentando cada
    una como historial real para la siguiente (igual que `predecir_semana` del
    notebook, generalizado a cualquier `dias`), y retorna el DataFrame de
    historial ya extendido con esos `dias` nuevos al final (no solo el resumen).

    Es el bloque de construccion tanto de `predict_range` (que solo necesita el
    resumen de los ultimos `dias`) como del relleno de huecos de calendario que
    hace `app.services.prediction_service` antes de construir features para una
    fecha lejana (sin este relleno, los lags saldrian mal: se calculan por
    POSICION de fila via `pandas.shift`, no por fecha real).

    `precio_medio` se fija una unica vez (ultimo valor conocido antes de
    `fecha_inicio`) y se mantiene constante todo el periodo.
    """
    precio_vigente = resolve_precio_medio(history_before, clasificador, fecha_inicio)
    historial = history_before.copy()

    for i in range(dias):
        fecha = fecha_inicio + pd.Timedelta(days=i)
        start = time.perf_counter()
        prediccion = predict_single_day(
            registry, historial, clasificador, fecha, precio_medio=precio_vigente
        )
        duration_ms = (time.perf_counter() - start) * 1000

        if on_day is not None:
            on_day(i, fecha, prediccion, duration_ms)

        historial = pd.concat(
            [
                historial,
                pd.DataFrame(
                    [
                        {
                            "clasificador": clasificador,
                            "dia": fecha,
                            "cantidad_vendida": prediccion,
                            "precio_medio": precio_vigente,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

    return historial


def predict_range(
    registry: MLModelRegistry,
    history_before: pd.DataFrame,
    clasificador: str,
    fecha_inicio: pd.Timestamp,
    dias: int,
    on_day: OnDayCallback | None = None,
) -> tuple[list[tuple[pd.Timestamp, int]], int]:
    """Predice `dias` consecutivos desde `fecha_inicio` y retorna el desglose +
    el total acumulado. `dias=7` es el caso semana; `dias=30` sirve para
    estimar el mes siguiente. Ver `extend_history_with_predictions` para el
    encadenado real; esta funcion solo recorta el resumen de los ultimos `dias`.
    """
    historial_extendido = extend_history_with_predictions(
        registry, history_before, clasificador, fecha_inicio, dias, on_day=on_day
    )
    cola = historial_extendido.tail(dias)
    predicciones = [
        (fecha, int(cantidad))
        for fecha, cantidad in zip(cola["dia"], cola["cantidad_vendida"], strict=True)
    ]
    total = int(cola["cantidad_vendida"].sum())
    return predicciones, total
