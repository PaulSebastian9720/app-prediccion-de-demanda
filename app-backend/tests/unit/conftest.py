"""Fixtures compartidas por los tests unitarios de `app.ml`."""

from pathlib import Path

import pytest

ARTIFACTS_ROOT = Path(__file__).resolve().parents[2] / "artifacts"


@pytest.fixture(scope="module")
def model_artifacts_dir() -> Path:
    """Carpeta con los 4 archivos del modelo activo -- resuelve tanto el
    layout plano legado (`artifacts/`) como el versionado
    (`artifacts/models/v001__.../`, tras correr
    `scripts/migrate_existing_model_to_versioned.py`), para que estos tests
    no dependan de si la migracion ya se corrio en este checkout."""
    models_dir = ARTIFACTS_ROOT / "models"
    if models_dir.exists():
        versiones = sorted(p for p in models_dir.iterdir() if p.is_dir())
        if versiones:
            return versiones[0]
    return ARTIFACTS_ROOT
