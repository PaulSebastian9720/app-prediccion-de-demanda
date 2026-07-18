"""Genera un CSV de ventas realista para subir via `/sales-history/upload`,
continuando desde el ULTIMO dia que ya existe en `sales_history` -- por
categoria, cada una puede tener un ultimo dia distinto -- hasta ayer. Nunca
regenera lo que ya existe: si una categoria ya esta al dia, se salta.

Los valores nuevos no son aleatorios puros: para cada categoria se calcula su
promedio/desviacion historica y un factor por dia de la semana (a partir de
sus propios datos ya cargados), y el precio evoluciona con un paso aleatorio
chico desde el ultimo precio conocido -- no un valor nuevo desconectado del
historico.

Uso: `uv run python scripts/generate_incremental_sales_csv.py [--out RUTA]`
"""

import argparse
import asyncio
import logging
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.config import get_settings
from app.db.session import create_engine, create_session_factory
from app.services.sales_history_service import get_all_history

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)

SEED = 42
COLUMNS = ["clasificador", "dia", "cantidad_vendida", "precio_medio"]


def _generar_para_clasificador(
    historial: pd.DataFrame, clasificador: str, hasta: date, rng: np.random.Generator
) -> pd.DataFrame:
    grupo = historial[historial["clasificador"] == clasificador].sort_values("dia")
    ultimo_dia = grupo["dia"].max().date()
    desde = ultimo_dia + timedelta(days=1)

    if desde > hasta:
        logger.info("%-30s ya esta al dia (ultimo dia %s) -- nada que generar.", clasificador, ultimo_dia)
        return pd.DataFrame(columns=COLUMNS)

    dow = grupo["dia"].dt.dayofweek
    media_global = float(grupo["cantidad_vendida"].mean())
    std_global = float(grupo["cantidad_vendida"].std(ddof=0) or media_global * 0.3) or 1.0
    factor_dow = (grupo.groupby(dow)["cantidad_vendida"].mean() / media_global).to_dict()
    precio_actual = float(grupo["precio_medio"].iloc[-1])

    filas = []
    fecha = desde
    while fecha <= hasta:
        factor = factor_dow.get(fecha.weekday(), 1.0)
        media_dia = max(1.0, media_global * factor)
        cantidad = max(0, int(round(rng.normal(media_dia, std_global * 0.6))))
        precio_actual *= 1 + rng.uniform(-0.015, 0.015)
        filas.append(
            {
                "clasificador": clasificador,
                "dia": fecha.isoformat(),
                "cantidad_vendida": cantidad,
                "precio_medio": round(precio_actual, 2),
            }
        )
        fecha += timedelta(days=1)

    logger.info(
        "%-30s %d dia(s) generado(s) (%s -> %s)", clasificador, len(filas), desde, hasta
    )
    return pd.DataFrame(filas, columns=COLUMNS)


async def main(output_path: Path) -> None:
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    async with session_factory() as db:
        historial = await get_all_history(db)
    await engine.dispose()

    if historial.empty:
        logger.error("'sales_history' esta vacio -- no hay un ultimo dia del que continuar.")
        return

    ayer = date.today() - timedelta(days=1)
    rng = np.random.default_rng(SEED)

    partes = [
        _generar_para_clasificador(historial, clasificador, ayer, rng)
        for clasificador in sorted(historial["clasificador"].unique())
    ]
    nuevas = pd.concat(partes, ignore_index=True)

    if nuevas.empty:
        logger.info("Todas las categorias ya estan al dia hasta %s -- no se genero ningun archivo.", ayer)
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    nuevas.to_csv(output_path, index=False)
    logger.info(
        "%d fila(s) nuevas escritas en '%s' -- listo para subir via /sales-history/upload.",
        len(nuevas),
        output_path,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Ruta del CSV de salida (default: scripts/output/ventas_nuevas_hasta_<ayer>.csv).",
    )
    args = parser.parse_args()

    default_path = Path(__file__).parent / "output" / f"ventas_nuevas_hasta_{date.today() - timedelta(days=1)}.csv"
    asyncio.run(main(args.out or default_path))
