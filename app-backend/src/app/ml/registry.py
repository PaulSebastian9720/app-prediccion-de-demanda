"""Carga y mantiene en memoria los artefactos del modelo de forecasting.

Los artefactos se cargan al arrancar la aplicacion (ver `app.main.lifespan`)
y se pueden RECARGAR en caliente durante la vida del proceso -- cuando un
reentrenamiento produce una version mejor (o un admin activa una version
distinta a mano, ver `app.services.retraining_service`), sin reiniciar el
servidor. Por eso los 4 artefactos viven en un `_RegistryBundle` inmutable
intercambiado atomicamente bajo un `threading.Lock`: es la primera vez que
este codigo tiene estado mutable compartido entre hilos (el reload corre en
un hilo de `asyncio.to_thread` mientras las requests leen desde el event
loop) -- un lock normal de asyncio no protegeria esa carrera.
"""

import json
import pickle
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import xgboost as xgb
from sklearn.preprocessing import OneHotEncoder


@dataclass(frozen=True)
class _RegistryBundle:
    model: xgb.XGBRegressor
    transformer: OneHotEncoder
    feature_cols: list[str]
    metadata: dict[str, Any]


class MLModelRegistry:
    """Contenedor de los artefactos del modelo XGBoost de forecasting de ventas."""

    def __init__(self, artifacts_dir: Path) -> None:
        self._artifacts_dir = artifacts_dir
        self._bundle: _RegistryBundle | None = None
        self._lock = threading.Lock()

    @staticmethod
    def _load_bundle(artifacts_dir: Path) -> _RegistryBundle:
        """Lectura pura desde `artifacts_dir`: no toca ningun estado compartido,
        puede correr fuera del lock (el lock solo protege el intercambio final)."""
        model = xgb.XGBRegressor()
        model.load_model(str(artifacts_dir / "xgboost_ventas.json"))

        with open(artifacts_dir / "transformer_clasificador.pkl", "rb") as f:
            transformer = pickle.load(f)  # noqa: S301 - artefacto propio, no de terceros

        with open(artifacts_dir / "feature_cols.pkl", "rb") as f:
            feature_cols = pickle.load(f)  # noqa: S301

        with open(artifacts_dir / "metadata_modelo.json", encoding="utf-8") as f:
            metadata = json.load(f)

        return _RegistryBundle(
            model=model, transformer=transformer, feature_cols=feature_cols, metadata=metadata
        )

    def load(self) -> None:
        """Carga los artefactos desde `self._artifacts_dir` (constructor). Es
        sincrona/CPU-bound a proposito: se invoca desde `lifespan()` envuelta
        en `asyncio.to_thread()` para no bloquear el event loop."""
        self.reload(self._artifacts_dir)

    def reload(self, new_dir: Path) -> None:
        """Carga los artefactos de `new_dir` y los intercambia atomicamente.

        Llamar siempre desde un hilo (`asyncio.to_thread`): `_load_bundle` hace
        I/O de disco. El lock solo se toma para el intercambio final del
        bundle, no durante la carga -- una request concurrente sigue leyendo
        el bundle viejo (consistente) hasta que el nuevo esta 100% listo.
        """
        bundle = self._load_bundle(new_dir)
        with self._lock:
            self._bundle = bundle
            self._artifacts_dir = new_dir

    @property
    def artifacts_dir(self) -> Path:
        """Carpeta que sirve el bundle actualmente cargado -- util para
        inspeccion/tests (ej. restaurar el estado original tras un `reload`
        de prueba), no se usa en el camino normal de prediccion."""
        with self._lock:
            return self._artifacts_dir

    def _get_bundle(self) -> _RegistryBundle:
        with self._lock:
            bundle = self._bundle
        assert bundle is not None, "El modelo no ha sido cargado. Llama a load() primero."
        return bundle

    @property
    def is_loaded(self) -> bool:
        with self._lock:
            return self._bundle is not None

    @property
    def model(self) -> xgb.XGBRegressor:
        return self._get_bundle().model

    @property
    def transformer(self) -> OneHotEncoder:
        return self._get_bundle().transformer

    @property
    def feature_cols(self) -> list[str]:
        return self._get_bundle().feature_cols

    @property
    def metadata(self) -> dict[str, Any]:
        return self._get_bundle().metadata

    @property
    def lags(self) -> list[int]:
        return list(self.metadata["lags_usados"])

    @property
    def historia_minima(self) -> int:
        return max(self.lags)

    @property
    def clasificadores_validos(self) -> list[str]:
        return list(self.metadata["clasificadores"])

    @property
    def model_version(self) -> str:
        return str(self.metadata.get("fecha_entrenamiento", "unknown"))

    def predict_raw(self, x: pd.DataFrame) -> float:
        """Ejecuta `model.predict` sobre una unica fila ya alineada a `feature_cols`.

        Es rapida (microsegundos) por lo que se llama de forma sincrona, sin
        `asyncio.to_thread`, a diferencia de la carga/recarga de artefactos.
        """
        prediction = self.model.predict(x)
        return float(prediction[0])
