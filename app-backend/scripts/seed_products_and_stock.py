"""Siembra `products` (precio/costo) e `inventory_stock` (stock inicial) por categoria.

`precio_venta` se calcula como el promedio historico real de
`sales_history.precio_medio` para cada categoria (no un numero arbitrario);
`costo_reposicion` se deriva con un margen tipico del 40% (`costo = 0.6 * precio`).

El stock inicial se deriva de la demanda diaria promedio historica, con dias
de cobertura CURADOS por categoria (no un numero uniforme): categorias de
rotacion rapida (comida, juguetes, transporte) quedan con cobertura baja
(reabastecimiento frecuente, realista) y categorias de rotacion lenta
(descanso, identificacion, vestimenta) quedan bien abastecidas — asi los
reportes muestran una mezcla real de prioridades Alta/Media/Baja en vez de
que todo salga igual. Todo es editable despues via `PATCH /products/...` y
`POST /inventory`.

Uso: `uv run python scripts/seed_products_and_stock.py` (o `make seed-catalog`).
"""

import asyncio
import logging

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import get_settings
from app.db.models.inventory_stock import InventoryStock
from app.db.models.product import Product
from app.db.models.sales_history import SalesHistory
from app.db.session import create_engine, create_session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)

NOMBRES_DISPLAY = {
    "ALIMENTACION_HIDRATACION": "Alimentacion e Hidratacion",
    "DESCANSO": "Descanso",
    "HIGIENE_ASEO": "Higiene y Aseo",
    "IDENTIFICACION_LOCALIZACION": "Identificacion y Localizacion",
    "JUGUETES": "Juguetes",
    "OTROS_ACCESORIOS": "Otros Accesorios",
    "PASEO_SUJECION": "Paseo y Sujecion",
    "TRANSPORTE_VIAJE": "Transporte y Viaje",
    "VESTIMENTA": "Vestimenta",
}

MARGEN_REPOSICION = 0.6  # costo_reposicion = 60% del precio de venta (~40% de margen)

# Dias de cobertura de `stock_actual` por categoria, curados a mano para que
# los reportes (semanal=7 dias, mensual=30 dias) muestren una mezcla real de
# prioridades en vez de que las 9 categorias salgan siempre "Baja". El umbral
# de prioridad Alta es la mitad del periodo del reporte (ver
# app/reports/metrics.py::_clasificar_prioridad): con 30 dias de referencia,
# <=15 dias de cobertura es Alta, <=30 es Media, mas de 30 es Baja.
DIAS_COBERTURA_ACTUAL_POR_CATEGORIA: dict[str, int] = {
    "JUGUETES": 3,  # rotacion muy rapida -> critico en ambos reportes
    "ALIMENTACION_HIDRATACION": 5,
    "TRANSPORTE_VIAJE": 6,
    "PASEO_SUJECION": 9,
    "HIGIENE_ASEO": 13,
    "OTROS_ACCESORIOS": 20,
    "IDENTIFICACION_LOCALIZACION": 28,
    "DESCANSO": 40,  # rotacion lenta -> bien abastecido
    "VESTIMENTA": 55,
}
DIAS_COBERTURA_STOCK_MINIMO = 6  # umbral de seguridad, constante entre categorias


async def main() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    async with session_factory() as db:
        stmt = select(
            SalesHistory.clasificador,
            func.avg(SalesHistory.precio_medio).label("precio_promedio"),
            func.avg(SalesHistory.cantidad_vendida).label("demanda_promedio_diaria"),
        ).group_by(SalesHistory.clasificador)
        rows = (await db.execute(stmt)).all()

        if not rows:
            logger.warning("sales_history esta vacio. Corre 'make seed' primero.")
            await engine.dispose()
            return

        product_payloads = []
        stock_payloads = []
        for clasificador, precio_promedio, demanda_promedio_diaria in rows:
            precio_venta = round(float(precio_promedio), 2)
            costo_reposicion = round(precio_venta * MARGEN_REPOSICION, 2)
            demanda_diaria = float(demanda_promedio_diaria)
            dias_cobertura = DIAS_COBERTURA_ACTUAL_POR_CATEGORIA.get(clasificador, 15)
            stock_actual = round(demanda_diaria * dias_cobertura, 1)
            stock_minimo = round(demanda_diaria * DIAS_COBERTURA_STOCK_MINIMO, 1)

            product_payloads.append(
                {
                    "clasificador": clasificador,
                    "nombre_display": NOMBRES_DISPLAY.get(clasificador, clasificador.title()),
                    "precio_venta": precio_venta,
                    "costo_reposicion": costo_reposicion,
                }
            )
            stock_payloads.append(
                {
                    "clasificador": clasificador,
                    "stock_actual": stock_actual,
                    "stock_minimo": stock_minimo,
                }
            )
            logger.info(
                "%-30s precio=%.2f costo_repo=%.2f stock_actual=%.1f stock_minimo=%.1f",
                clasificador,
                precio_venta,
                costo_reposicion,
                stock_actual,
                stock_minimo,
            )

        product_stmt = pg_insert(Product)
        product_stmt = product_stmt.on_conflict_do_update(
            index_elements=["clasificador"],
            set_={
                "nombre_display": product_stmt.excluded.nombre_display,
                "precio_venta": product_stmt.excluded.precio_venta,
                "costo_reposicion": product_stmt.excluded.costo_reposicion,
            },
        )
        await db.execute(product_stmt, product_payloads)

        stock_stmt = pg_insert(InventoryStock)
        stock_stmt = stock_stmt.on_conflict_do_update(
            index_elements=["clasificador"],
            set_={
                "stock_actual": stock_stmt.excluded.stock_actual,
                "stock_minimo": stock_stmt.excluded.stock_minimo,
            },
        )
        await db.execute(stock_stmt, stock_payloads)

        await db.commit()

    logger.info("Catalogo de productos y stock sembrado (%d categorias).", len(rows))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
