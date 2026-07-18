"""Tests unitarios de `app.ml.training` -- dataset sintetico chico para que
`RandomizedSearchCV`+`TimeSeriesSplit` corran en milisegundos."""

import numpy as np
import pandas as pd
import pytest

from app.core.exceptions import InsufficientTrainingDataError
from app.ml.training import (
    MIN_DIAS_POR_CLASIFICADOR,
    build_training_frame,
    train_new_model,
)

CLASIFICADORES = ["ALIMENTACION_HIDRATACION", "JUGUETES", "VESTIMENTA"]
LAGS = [1, 2, 3, 4, 5, 6, 7, 14, 21]


def _synthetic_history(dias: int = 60, clasificadores: list[str] = CLASIFICADORES) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    fechas = pd.date_range("2026-01-01", periods=dias, freq="D")
    filas = []
    for clasificador in clasificadores:
        base = rng.integers(10, 40)
        for fecha in fechas:
            filas.append(
                {
                    "clasificador": clasificador,
                    "dia": fecha,
                    "cantidad_vendida": max(0, int(base + rng.normal(0, 5))),
                    "precio_medio": 10.0,
                }
            )
    return pd.DataFrame(filas)


def test_build_training_frame_drops_rows_missing_max_lag() -> None:
    history = _synthetic_history(dias=30, clasificadores=["JUGUETES"])
    datos = build_training_frame(history, LAGS)

    historia_minima = max(LAGS)
    assert len(datos) == 30 - historia_minima
    assert not datos[f"lag_{historia_minima}"].isna().any()


def test_build_training_frame_empty_history_returns_empty_frame() -> None:
    history = pd.DataFrame(columns=["clasificador", "dia", "cantidad_vendida", "precio_medio"])
    datos = build_training_frame(history, LAGS)
    assert datos.empty


def test_train_new_model_end_to_end() -> None:
    history = _synthetic_history(dias=60)

    result = train_new_model(history, lags=LAGS, seed=42)

    assert result.feature_cols
    assert len(result.feature_cols) == result.metadata["n_features"]
    assert set(result.metadata["clasificadores"]) == set(CLASIFICADORES)
    for particion in ("validacion", "prueba"):
        metricas = result.metadata["metricas"][particion]
        assert set(metricas) == {"MAE", "RMSE", "R2"}
        assert metricas["MAE"] >= 0


def test_train_new_model_raises_if_clasificador_has_too_little_history() -> None:
    history = _synthetic_history(dias=60, clasificadores=["JUGUETES"])
    poco_historial = _synthetic_history(dias=MIN_DIAS_POR_CLASIFICADOR - 5, clasificadores=["VESTIMENTA"])
    history = pd.concat([history, poco_historial], ignore_index=True)

    with pytest.raises(InsufficientTrainingDataError):
        train_new_model(history, lags=LAGS, seed=42)


def test_train_new_model_raises_on_empty_history() -> None:
    history = pd.DataFrame(columns=["clasificador", "dia", "cantidad_vendida", "precio_medio"])
    with pytest.raises(InsufficientTrainingDataError):
        train_new_model(history, lags=LAGS, seed=42)
