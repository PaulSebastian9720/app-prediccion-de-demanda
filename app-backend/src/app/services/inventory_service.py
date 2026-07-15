"""Consulta y actualizacion del inventario/stock actual por categoria."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.inventory_stock import InventoryStock
from app.schemas.inventory import InventoryStockUpsertRequest
from app.schemas.sales_history import BulkUpsertResponse, RowError


async def list_stock(db: AsyncSession) -> list[InventoryStock]:
    rows = (
        (await db.execute(select(InventoryStock).order_by(InventoryStock.clasificador)))
        .scalars()
        .all()
    )
    return list(rows)


async def get_stock_map(db: AsyncSession) -> dict[str, InventoryStock]:
    """Todo el stock indexado por `clasificador` (usado por el generador de reportes)."""
    return {row.clasificador: row for row in await list_stock(db)}


async def upsert_stock(
    db: AsyncSession,
    records: list[InventoryStockUpsertRequest],
    valid_clasificadores: set[str],
) -> BulkUpsertResponse:
    """Inserta o actualiza (`ON CONFLICT (clasificador) DO UPDATE`) un lote de registros.

    Filas con un `clasificador` fuera de `valid_clasificadores` se rechazan
    (reportadas en `errors`) sin abortar el resto del lote -- mismo criterio
    que `sales_history_service.upsert_records`, para que la subida de archivo
    tenga la misma UX de exito parcial en ambos casos.
    """
    errors: list[RowError] = []
    payloads: list[dict[str, object]] = []

    for idx, record in enumerate(records):
        if record.clasificador not in valid_clasificadores:
            errors.append(
                RowError(
                    row=idx,
                    reason=(
                        f"Clasificador desconocido: '{record.clasificador}'. "
                        f"Validos: {sorted(valid_clasificadores)}"
                    ),
                )
            )
            continue
        payloads.append(
            {
                "clasificador": record.clasificador,
                "stock_actual": record.stock_actual,
                "stock_minimo": record.stock_minimo,
            }
        )

    if payloads:
        stmt = pg_insert(InventoryStock)
        stmt = stmt.on_conflict_do_update(
            index_elements=["clasificador"],
            set_={
                "stock_actual": stmt.excluded.stock_actual,
                "stock_minimo": stmt.excluded.stock_minimo,
            },
        )
        await db.execute(stmt, payloads)
        await db.commit()

    return BulkUpsertResponse(
        rows_received=len(records),
        rows_upserted=len(payloads),
        rows_rejected=len(errors),
        errors=errors,
    )
