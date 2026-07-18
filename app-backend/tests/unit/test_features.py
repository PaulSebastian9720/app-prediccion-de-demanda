"""Tests unitarios del pipeline de features/inferencia contra los valores de
referencia calculados en `notebooks/03_prediccion.ipynb` para el caso
`PASEO_SUJECION`.
"""

from pathlib import Path

import pandas as pd
import pytest

from app.ml.features import predict_range, predict_single_day
from app.ml.registry import MLModelRegistry

ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts"


@pytest.fixture(scope="module")
def registry(model_artifacts_dir: Path) -> MLModelRegistry:
    reg = MLModelRegistry(model_artifacts_dir)
    reg.load()
    return reg


@pytest.fixture(scope="module")
def panel() -> pd.DataFrame:
    return pd.read_csv(ARTIFACTS_DIR / "dataset_diario_series_temporales.csv", parse_dates=["dia"])


def _history_before(panel: pd.DataFrame, clasificador: str, fecha: pd.Timestamp) -> pd.DataFrame:
    return panel[(panel["clasificador"] == clasificador) & (panel["dia"] < fecha)][
        ["clasificador", "dia", "cantidad_vendida", "precio_medio"]
    ].copy()


def test_predict_single_day_test_case(registry: MLModelRegistry, panel: pd.DataFrame) -> None:
    clasificador = "PASEO_SUJECION"
    fecha = pd.Timestamp("2026-07-02")
    historial = _history_before(panel, clasificador, fecha)

    prediccion = predict_single_day(registry, historial, clasificador, fecha)

    assert prediccion == 17


def test_predict_range_week_test_case(registry: MLModelRegistry, panel: pd.DataFrame) -> None:
    clasificador = "PASEO_SUJECION"
    fecha_inicio = pd.Timestamp("2026-07-02")
    historial = _history_before(panel, clasificador, fecha_inicio)

    predicciones, total = predict_range(registry, historial, clasificador, fecha_inicio, dias=7)

    assert len(predicciones) == 7
    assert total == 214


def test_predict_single_day_future_case(registry: MLModelRegistry, panel: pd.DataFrame) -> None:
    clasificador = "PASEO_SUJECION"
    fecha_max = panel["dia"].max()
    fecha_futura = fecha_max + pd.Timedelta(days=1)
    historial = _history_before(panel, clasificador, fecha_futura)

    prediccion = predict_single_day(registry, historial, clasificador, fecha_futura)

    assert prediccion == 36


def test_predict_range_week_future_case(registry: MLModelRegistry, panel: pd.DataFrame) -> None:
    clasificador = "PASEO_SUJECION"
    fecha_max = panel["dia"].max()
    fecha_futura = fecha_max + pd.Timedelta(days=1)
    historial = _history_before(panel, clasificador, fecha_futura)

    _, total = predict_range(registry, historial, clasificador, fecha_futura, dias=7)

    assert total == 209


def test_on_day_callback_invoked_per_day(registry: MLModelRegistry, panel: pd.DataFrame) -> None:
    clasificador = "PASEO_SUJECION"
    fecha_inicio = pd.Timestamp("2026-07-02")
    historial = _history_before(panel, clasificador, fecha_inicio)

    eventos: list[tuple[int, pd.Timestamp, int, float]] = []
    predict_range(
        registry,
        historial,
        clasificador,
        fecha_inicio,
        dias=3,
        on_day=lambda i, fecha, pred, dur: eventos.append((i, fecha, pred, dur)),
    )

    assert len(eventos) == 3
    assert [e[0] for e in eventos] == [0, 1, 2]
