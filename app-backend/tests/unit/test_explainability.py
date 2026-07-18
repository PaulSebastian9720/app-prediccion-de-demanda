"""Tests unitarios de la explicabilidad (XAI) de una prediccion individual.

Usa el mismo caso de referencia que `tests/unit/test_features.py`
(`PASEO_SUJECION` en 2026-07-02, prediccion == 17) para poder razonar sobre
los deltas de perturbacion con numeros conocidos.
"""

from pathlib import Path

import pandas as pd
import pytest

from app.ml import explainability, features
from app.ml.registry import MLModelRegistry

ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts"
CLASIFICADOR = "PASEO_SUJECION"
FECHA = pd.Timestamp("2026-07-02")


@pytest.fixture(scope="module")
def registry(model_artifacts_dir: Path) -> MLModelRegistry:
    reg = MLModelRegistry(model_artifacts_dir)
    reg.load()
    return reg


@pytest.fixture(scope="module")
def panel() -> pd.DataFrame:
    return pd.read_csv(ARTIFACTS_DIR / "dataset_diario_series_temporales.csv", parse_dates=["dia"])


@pytest.fixture(scope="module")
def history_before(panel: pd.DataFrame) -> pd.DataFrame:
    return panel[(panel["clasificador"] == CLASIFICADOR) & (panel["dia"] < FECHA)][
        ["clasificador", "dia", "cantidad_vendida", "precio_medio"]
    ].copy()


@pytest.fixture(scope="module")
def fila_y_x(
    registry: MLModelRegistry, history_before: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    fila = features.build_feature_row(
        history_before, CLASIFICADOR, FECHA, registry.lags, registry.historia_minima
    )
    x = features.encode_and_align(fila, registry)
    prediccion = features.postprocess_prediction(features.predict_log_value(registry, x))
    return fila, x, prediccion


def test_prediccion_de_referencia_no_cambia(fila_y_x: tuple[pd.DataFrame, pd.DataFrame, int]) -> None:
    """Ancla el fixture al mismo valor de referencia que `test_features.py`."""
    _, _, prediccion = fila_y_x
    assert prediccion == 17


def test_rank_contribuciones_solo_incluye_variables_perturbables(
    registry: MLModelRegistry, fila_y_x: tuple[pd.DataFrame, pd.DataFrame, int]
) -> None:
    _, x, _ = fila_y_x
    ranking = explainability.rank_contribuciones(registry, x)

    assert ranking  # el dataset tiene suficiente senal como para que algo rankee
    assert set(ranking).issubset(explainability._NEUTRAL_VALUE.keys())
    assert len(ranking) == len(set(ranking))  # sin duplicados


def test_explicar_por_perturbacion_delta_cuadra_con_la_prediccion(
    registry: MLModelRegistry, fila_y_x: tuple[pd.DataFrame, pd.DataFrame, int]
) -> None:
    """El delta de cada factor debe ser el que, restado, reproduce EXACTAMENTE
    la prediccion recalculada con esa variable en su valor neutro -- no una
    aproximacion en escala log."""
    fila, x, prediccion = fila_y_x
    ranking = explainability.rank_contribuciones(registry, x)

    factores = explainability.explicar_por_perturbacion(registry, fila, prediccion, ranking)

    assert 0 <= len(factores) <= explainability.MAX_FACTORES
    for nombre, delta in factores:
        assert nombre in explainability.FEATURE_LABELS
        assert delta != 0  # los deltas nulos se descartan, no aportan una frase util

        neutro = explainability._NEUTRAL_VALUE[nombre]
        fila_mod = fila.copy()
        fila_mod[nombre] = fila[neutro].iloc[0] if isinstance(neutro, str) else neutro
        x_mod = features.encode_and_align(fila_mod, registry)
        pred_mod = features.postprocess_prediction(features.predict_log_value(registry, x_mod))

        assert prediccion - pred_mod == delta


def test_dia_similar_mas_cercano_devuelve_un_dia_pasado_del_mismo_dow(
    history_before: pd.DataFrame, fila_y_x: tuple[pd.DataFrame, pd.DataFrame, int]
) -> None:
    fila, _, _ = fila_y_x
    dow = int(fila["dow"].iloc[0])
    lag_1 = float(fila["lag_1"].iloc[0])
    lag_7 = float(fila["lag_7"].iloc[0])

    resultado = explainability.dia_similar_mas_cercano(history_before, dow, lag_1, lag_7)

    assert resultado is not None
    fecha_similar, cantidad_similar = resultado
    assert fecha_similar < FECHA
    assert fecha_similar.dayofweek == dow
    assert cantidad_similar >= 0


def test_dia_similar_mas_cercano_sin_historial_devuelve_none() -> None:
    vacio = pd.DataFrame(columns=["clasificador", "dia", "cantidad_vendida", "precio_medio"])
    vacio["dia"] = pd.to_datetime(vacio["dia"])
    assert explainability.dia_similar_mas_cercano(vacio, dow=4, lag_1=10.0, lag_7=8.0) is None
