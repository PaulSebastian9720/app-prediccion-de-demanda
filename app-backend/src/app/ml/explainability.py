"""Explicabilidad (XAI) de una prediccion individual (endpoint /predictions/day).

Separa deliberadamente dos preguntas distintas, para no caer en la trampa de
convertir `pred_contribs` directamente en unidades: el modelo se entrena sobre
`log1p(cantidad_vendida)` (ver `features.postprocess_prediction`), y las
contribuciones de XGBoost son aditivas en esa escala logaritmica — `expm1` no
es lineal, asi que sumar cada contribucion por separado y convertirla no
cuadra con la prediccion final.

- `rank_contribuciones`: usa `pred_contribs` (equivalente a SHAP, sin libreria
  extra) SOLO para decidir que variables importan mas y en que direccion.
- `explicar_por_perturbacion`: mide el efecto real en unidades recalculando la
  prediccion con esa variable en un valor "neutro" (perturbacion), reutilizando
  las mismas funciones puras de `features.py` que ya usa el pipeline — el
  delta resultante SI cuadra con la prediccion final, porque se calcula
  post-`expm1`, no en log-space.
"""

import pandas as pd
import xgboost as xgb

from app.ml import features
from app.ml.registry import MLModelRegistry

# Nombre legible en espanol, por variable perturbable (solo las que tienen un
# valor "neutro" interpretable para un cliente sin conocimientos tecnicos;
# el resto de columnas -- one-hot de clasificador, senos/cosenos de calendario,
# medias expansivas -- se dejan fuera de la explicacion aunque influyan en el
# modelo, porque no se traducen en una frase clara).
FEATURE_LABELS: dict[str, str] = {
    "lag_1": "Ventas de ayer",
    "lag_7": "Ventas de hace una semana",
    "lag_14": "Ventas de hace dos semanas",
    "es_fin_de_semana": "Cercania al fin de semana",
    "es_viernes": "Ser viernes",
    "es_lunes": "Ser lunes",
    "diff_semana": "Diferencia con la semana pasada",
}

# Valor "neutro" para cada variable perturbable: el nombre de OTRA columna ya
# presente en la fila (su contraparte semantica "tipica"), o un literal.
_NEUTRAL_VALUE: dict[str, str | float] = {
    "lag_1": "roll_mean_7",
    "lag_7": "roll_mean_14",
    "lag_14": "roll_mean_14",
    "es_fin_de_semana": 0,
    "es_viernes": 0,
    "es_lunes": 0,
    "diff_semana": 0.0,
}

MAX_FACTORES = 3


def rank_contribuciones(registry: MLModelRegistry, x: pd.DataFrame) -> list[str]:
    """Ordena las variables PERTURBABLES por `|pred_contribs|` (escala log1p),
    de mayor a menor relevancia. Se usa solo para decidir que perturbar despues
    -- nunca para reportar una cifra en unidades directamente."""
    dmatrix = xgb.DMatrix(x, feature_names=list(x.columns))
    contribs = registry.model.get_booster().predict(dmatrix, pred_contribs=True)
    fila = contribs[0][:-1]  # la ultima columna es el bias/base_value; se descarta
    pares = list(zip(x.columns, fila, strict=True))
    perturbables = [(nombre, valor) for nombre, valor in pares if nombre in _NEUTRAL_VALUE]
    perturbables.sort(key=lambda par: abs(par[1]), reverse=True)
    return [nombre for nombre, _ in perturbables]


def explicar_por_perturbacion(
    registry: MLModelRegistry,
    fila_base: pd.DataFrame,
    prediccion_base: int,
    variables_a_perturbar: list[str],
) -> list[tuple[str, int]]:
    """Para cada variable en `variables_a_perturbar` (ya ordenadas por
    relevancia), recalcula la prediccion con esa variable en su valor neutro y
    retorna `(nombre_variable, delta_unidades)`: el efecto real en unidades,
    ya en la misma escala que `prediccion_base` (post-postprocess).

    Descarta variables cuyo delta es 0 (la perturbacion no cambio nada, no
    aportan una frase util) y se detiene en `MAX_FACTORES` resultados.
    """
    resultados: list[tuple[str, int]] = []
    for nombre in variables_a_perturbar:
        if len(resultados) >= MAX_FACTORES:
            break
        neutro = _NEUTRAL_VALUE[nombre]
        fila_mod = fila_base.copy()
        fila_mod[nombre] = fila_base[neutro].iloc[0] if isinstance(neutro, str) else neutro
        x_mod = features.encode_and_align(fila_mod, registry)
        pred_mod = features.postprocess_prediction(features.predict_log_value(registry, x_mod))
        delta = prediccion_base - pred_mod
        if delta != 0:
            resultados.append((nombre, delta))
    return resultados


def dia_similar_mas_cercano(
    history: pd.DataFrame, dow: int, lag_1: float, lag_7: float
) -> tuple[pd.Timestamp, int] | None:
    """Dia pasado del mismo dia de la semana cuyo propio patron reciente (venta
    del dia anterior + de hace 7 dias) se parece mas a `(lag_1, lag_7)`.

    Los lags se calculan sobre el historico COMPLETO ordenado por fecha antes
    de filtrar por dia de la semana (no shifteando dentro del subconjunto ya
    filtrado), para que representen lo mismo que `lag_1`/`lag_7` del dia
    objetivo: la venta real del dia y la semana inmediatamente anteriores.
    """
    h = history.sort_values("dia").reset_index(drop=True)
    h["_lag_1"] = h["cantidad_vendida"].shift(1)
    h["_lag_7"] = h["cantidad_vendida"].shift(7)

    candidatos = h[h["dia"].dt.dayofweek == dow].dropna(subset=["_lag_1", "_lag_7"]).copy()
    if candidatos.empty:
        return None

    candidatos["_dist"] = (candidatos["_lag_1"] - lag_1).abs() + (candidatos["_lag_7"] - lag_7).abs()
    mejor = candidatos.nsmallest(1, "_dist").iloc[0]
    return mejor["dia"], int(mejor["cantidad_vendida"])
