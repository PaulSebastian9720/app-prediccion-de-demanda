"""Puerto fiel del entrenamiento de `notebooks/02_XGBoost_entrenamiento.ipynb`.

A diferencia del notebook (que lee un CSV estatico), la fuente de datos aqui
es siempre `history`, un `DataFrame` con TODO el `sales_history` ya ingerido
por la app (ver `app.services.sales_history_service.get_all_history`) -- asi
cualquier dato nuevo cargado en "Datos y Modelo" efectivamente alimenta el
proximo reentrenamiento, algo que el notebook (contra un CSV fijo) nunca hizo.

Funcion sincrona y CPU-bound a proposito: se invoca desde
`app.services.retraining_service` envuelta en `asyncio.to_thread`, igual que
`MLModelRegistry.load()` en el arranque de la app.
"""

import json
import pickle
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from sklearn.preprocessing import OneHotEncoder

from app.core.exceptions import InsufficientTrainingDataError
from app.ml.features import build_group_features

LAGS_DEFAULT = [1, 2, 3, 4, 5, 6, 7, 14, 21]
SEED = 42

# Mismo espacio de busqueda que el notebook -- no se cambia sin re-validar
# aparte, es la unica referencia probada de que estos rangos funcionan bien
# para este dataset.
_ESPACIO_BUSQUEDA: dict[str, list[float]] = {
    "max_depth": [3, 4, 5, 6],
    "learning_rate": [0.01, 0.03, 0.05, 0.1],
    "subsample": [0.7, 0.8, 0.9, 1.0],
    "colsample_bytree": [0.6, 0.7, 0.8, 1.0],
    "min_child_weight": [1, 3, 5, 10],
    "reg_lambda": [0.5, 1.0, 2.0, 5.0],
}

# Guardas contra historial insuficiente -- sin esto, un clasificador nuevo con
# pocos dias de historia (o un `sales_history` global todavia chico) haria
# fallar RandomizedSearchCV/TimeSeriesSplit con una excepcion opaca de sklearn
# en vez de un error de dominio legible.
MIN_DIAS_POR_CLASIFICADOR = 30
MIN_FILAS_ENTRENAMIENTO = 10


@dataclass
class TrainingResult:
    model: xgb.XGBRegressor
    transformer: OneHotEncoder
    feature_cols: list[str]
    metadata: dict[str, Any]


def build_training_frame(history: pd.DataFrame, lags: list[int]) -> pd.DataFrame:
    """Agrupa `history` por clasificador, aplica `build_group_features` a cada
    grupo (lags, rolling stats, features de calendario) y descarta las filas
    sin `lag_{max(lags)}` -- mismo criterio que `construir_features` del
    notebook, solo reorganizado para reusar la funcion que ya sirve inferencia."""
    historia_minima = max(lags)
    grupos = [
        build_group_features(grupo, lags)
        for _, grupo in history.groupby("clasificador", group_keys=False)
    ]
    if not grupos:
        return pd.DataFrame(columns=[*history.columns, f"lag_{historia_minima}"])
    datos = pd.concat(grupos, ignore_index=True)
    return datos.dropna(subset=[f"lag_{historia_minima}"]).reset_index(drop=True)


def _calcular_metricas(y_real_log: pd.Series, y_pred_log: np.ndarray) -> dict[str, float]:
    y_real = np.expm1(y_real_log)
    y_pred = np.clip(np.expm1(y_pred_log), 0, None)
    return {
        "MAE": float(mean_absolute_error(y_real, y_pred)),
        "RMSE": float(np.sqrt(mean_squared_error(y_real, y_pred))),
        "R2": float(r2_score(y_real, y_pred)),
    }


def train_new_model(
    history: pd.DataFrame, lags: list[int] | None = None, seed: int = SEED
) -> TrainingResult:
    """Reentrena desde cero con TODO `history` (nunca fine-tuning incremental
    sobre el modelo anterior): mismo enfoque que el notebook -- RandomizedSearchCV
    con TimeSeriesSplit sobre el historial completo -- que en este dataset
    (chico) corre en segundos/pocos minutos, sin necesidad real de calentar el
    modelo previo.

    Levanta `InsufficientTrainingDataError` si algun clasificador no llega a
    `MIN_DIAS_POR_CLASIFICADOR` dias utilizables, o si la particion de
    entrenamiento resultante es demasiado chica para `TimeSeriesSplit(n_splits=3)`
    -- nunca debe fallar con una excepcion opaca de sklearn/xgboost.
    """
    lags = lags if lags is not None else LAGS_DEFAULT
    historia_minima = max(lags)

    datos = build_training_frame(history, lags)
    if datos.empty:
        raise InsufficientTrainingDataError(
            f"No hay filas con al menos {historia_minima} dias de historia previa "
            "para entrenar (sales_history vacio o insuficiente)."
        )

    conteos = datos["clasificador"].value_counts()
    insuficientes = conteos[conteos < MIN_DIAS_POR_CLASIFICADOR]
    if not insuficientes.empty:
        raise InsufficientTrainingDataError(
            "Historial insuficiente para entrenar (minimo "
            f"{MIN_DIAS_POR_CLASIFICADOR} dias utilizables por categoria): "
            f"{dict(insuficientes)}"
        )

    transformer = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
    codificado = transformer.fit_transform(datos[["clasificador"]])
    columnas_clasificador = transformer.get_feature_names_out(["clasificador"])
    datos_codificados = pd.DataFrame(
        codificado, columns=columnas_clasificador, index=datos.index
    )
    datos = pd.concat([datos, datos_codificados], axis=1)

    columnas_meta = ["clasificador", "dia", "cantidad_vendida"]
    feature_cols = [c for c in datos.columns if c not in columnas_meta]

    dias_unicos = np.sort(datos["dia"].unique())
    n = len(dias_unicos)
    corte_train = dias_unicos[int(n * 0.70) - 1]
    corte_val = dias_unicos[int(n * 0.85) - 1]

    train = datos[datos["dia"] <= corte_train]
    val = datos[(datos["dia"] > corte_train) & (datos["dia"] <= corte_val)]
    test = datos[datos["dia"] > corte_val]

    if len(train) < MIN_FILAS_ENTRENAMIENTO or val.empty or test.empty:
        raise InsufficientTrainingDataError(
            f"Historial insuficiente para dividir en entrenamiento/validacion/prueba "
            f"(filas: train={len(train)}, val={len(val)}, test={len(test)})."
        )

    train_x, train_y = train[feature_cols], np.log1p(train["cantidad_vendida"])
    val_x, val_y = val[feature_cols], np.log1p(val["cantidad_vendida"])
    test_x, test_y = test[feature_cols], np.log1p(test["cantidad_vendida"])

    estimador_base = xgb.XGBRegressor(
        n_estimators=400, objective="reg:absoluteerror", random_state=seed
    )
    busqueda = RandomizedSearchCV(
        estimador_base,
        param_distributions=_ESPACIO_BUSQUEDA,
        n_iter=18,
        scoring="neg_mean_absolute_error",
        cv=TimeSeriesSplit(n_splits=3),
        random_state=seed,
        n_jobs=-1,
    )
    busqueda.fit(train_x, train_y)
    mejores_parametros = busqueda.best_params_

    modelo = xgb.XGBRegressor(
        n_estimators=10000,
        objective="reg:absoluteerror",
        eval_metric="mae",
        early_stopping_rounds=50,
        random_state=seed,
        **mejores_parametros,
    )
    modelo.fit(
        train_x, train_y, eval_set=[(train_x, train_y), (val_x, val_y)], verbose=False
    )

    pred_val_log = modelo.predict(val_x)
    pred_test_log = modelo.predict(test_x)

    importancia_gain = modelo.get_booster().get_score(importance_type="gain")
    importancia_top15 = (
        pd.Series(importancia_gain).sort_values(ascending=False).head(15).round(2).to_dict()
    )

    metadata = {
        "fecha_entrenamiento": datetime.now().isoformat(timespec="seconds"),
        "n_features": len(feature_cols),
        "feature_cols": feature_cols,
        "clasificadores": sorted(datos["clasificador"].unique().tolist()),
        "lags_usados": lags,
        "hiperparametros": mejores_parametros,
        "metricas": {
            "validacion": _calcular_metricas(val_y, pred_val_log),
            "prueba": _calcular_metricas(test_y, pred_test_log),
        },
        "feature_importance_top15": importancia_top15,
    }

    return TrainingResult(
        model=modelo, transformer=transformer, feature_cols=feature_cols, metadata=metadata
    )


def save_training_result(result: TrainingResult, output_dir: Path) -> None:
    """Escribe los 4 archivos (mismos nombres que siempre carga `MLModelRegistry`)
    en `output_dir`, creando la carpeta si hace falta. I/O puro, se llama desde
    el hilo de `asyncio.to_thread` junto con `train_new_model`."""
    output_dir.mkdir(parents=True, exist_ok=True)

    result.model.save_model(str(output_dir / "xgboost_ventas.json"))

    with open(output_dir / "transformer_clasificador.pkl", "wb") as f:
        pickle.dump(result.transformer, f)

    with open(output_dir / "feature_cols.pkl", "wb") as f:
        pickle.dump(result.feature_cols, f)

    with open(output_dir / "metadata_modelo.json", "w", encoding="utf-8") as f:
        json.dump(result.metadata, f, indent=2, ensure_ascii=False)
