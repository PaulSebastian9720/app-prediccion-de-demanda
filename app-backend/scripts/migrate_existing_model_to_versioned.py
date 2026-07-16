"""Migra el modelo actual (layout plano en `artifacts/`) al layout versionado
(`artifacts/models/v001__.../`), insertando la fila `model_versions` (activa)
correspondiente.

Se corre UNA sola vez, a mano: `uv run python scripts/migrate_existing_model_to_versioned.py`
(o `make migrate-model`). Idempotente: si ya se corrio (existe `artifacts/models/`
con contenido, o no hay nada en el layout plano que migrar), no hace nada.
"""

import asyncio
import json
import logging
import shutil
from datetime import datetime

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models.model_version import ModelVersion
from app.db.session import create_engine, create_session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)

ARCHIVOS_MODELO = [
    "xgboost_ventas.json",
    "transformer_clasificador.pkl",
    "feature_cols.pkl",
    "metadata_modelo.json",
]


async def main() -> None:
    settings = get_settings()
    artifacts_dir = settings.model_artifacts_dir
    models_dir = artifacts_dir / "models"
    legacy_metadata = artifacts_dir / "metadata_modelo.json"

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    ya_movido = models_dir.exists() and any(models_dir.iterdir())

    if ya_movido:
        # Corrida anterior parcial (ej. la BD no estaba arriba cuando esto
        # corrio la primera vez): los archivos ya estan en su carpeta
        # versionada, solo falta la fila de 'model_versions'. Lee la
        # metadata de ahi, no del layout plano (que ya no existe).
        destino = sorted(p for p in models_dir.iterdir() if p.is_dir())[0]
        logger.info("'%s' ya tiene contenido -- se salta el movimiento de archivos.", models_dir)
    else:
        if not legacy_metadata.exists():
            logger.info(
                "No existe '%s' (layout plano legado) -- instalacion nueva, nada que migrar.",
                legacy_metadata,
            )
            await engine.dispose()
            return

        faltantes = [f for f in ARCHIVOS_MODELO if not (artifacts_dir / f).exists()]
        if faltantes:
            logger.error("Faltan archivos del modelo legado en '%s': %s", artifacts_dir, faltantes)
            await engine.dispose()
            return

        with open(legacy_metadata, encoding="utf-8") as f:
            metadata_legado = json.load(f)
        compacta = str(metadata_legado["fecha_entrenamiento"]).replace("-", "").replace(":", "")
        destino = models_dir / f"v001__{compacta}"
        destino.mkdir(parents=True, exist_ok=True)
        for nombre in ARCHIVOS_MODELO:
            shutil.move(str(artifacts_dir / nombre), str(destino / nombre))
        logger.info("Archivos movidos a '%s'.", destino)

    with open(destino / "metadata_modelo.json", encoding="utf-8") as f:
        metadata = json.load(f)

    # Independiente de si los archivos ya estaban movidos o no: si la fila de
    # 'model_versions' quedo pendiente, se inserta ahora sin volver a mover nada.
    async with session_factory() as db:
        existente = (
            await db.execute(select(ModelVersion).where(ModelVersion.version_number == 1))
        ).scalar_one_or_none()
        if existente is None:
            version = ModelVersion(
                version_number=1,
                fecha_entrenamiento=datetime.fromisoformat(str(metadata["fecha_entrenamiento"])),
                artifacts_dir=f"models/{destino.name}",
                metrics=metadata["metricas"],
                is_active=True,
                retraining_job_id=None,
            )
            db.add(version)
            await db.commit()
            logger.info("Version v1 registrada en 'model_versions' (activa).")
        else:
            logger.info("Ya existe una fila 'model_versions' con version_number=1. Nada que insertar.")

    await engine.dispose()
    logger.info("Migracion completada.")


if __name__ == "__main__":
    asyncio.run(main())
