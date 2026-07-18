"""Carga `dataset_diario_series_temporales.csv` en la tabla `sales_history`.

Uso: `uv run python scripts/seed_sales_history.py` (o `make seed`).
Idempotente: usa upsert por `(clasificador, dia)`, por lo que puede correrse
multiples veces sin duplicar datos ni fallar si ya existen filas.
"""

import asyncio
import json
import logging

import pandas as pd

from app.core.config import get_settings
from app.db.session import create_engine, create_session_factory
from app.schemas.sales_history import SalesRecordIn
from app.services.sales_history_service import upsert_records

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    csv_path = settings.model_artifacts_dir / "dataset_diario_series_temporales.csv"
    metadata_path = settings.model_artifacts_dir / "metadata_modelo.json"

    with open(metadata_path, encoding="utf-8") as f:
        metadata = json.load(f)
    valid_clasificadores = set(metadata["clasificadores"])

    df = pd.read_csv(csv_path, parse_dates=["dia"])
    records = [
        SalesRecordIn(
            clasificador=row.clasificador,
            dia=row.dia.date(),
            cantidad_vendida=row.cantidad_vendida,
            precio_medio=row.precio_medio,
        )
        for row in df.itertuples(index=False)
    ]
    logger.info("Leidos %d registros de %s", len(records), csv_path)

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    async with session_factory() as db:
        result = await upsert_records(db, records, valid_clasificadores)

    logger.info(
        "Seed completado: recibidos=%d upserted=%d rechazados=%d",
        result.rows_received,
        result.rows_upserted,
        result.rows_rejected,
    )
    for error in result.errors:
        logger.warning("Fila %d rechazada: %s", error.row, error.reason)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
