"""Consulta e ingesta del historico de ventas (`sales_history`)."""

from datetime import date

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sales_history import SalesHistory
from app.schemas.sales_history import BulkUpsertResponse, RowError, SalesRecordIn

HISTORY_COLUMNS = ["clasificador", "dia", "cantidad_vendida", "precio_medio"]


async def get_history_before(db: AsyncSession, clasificador: str, fecha: date) -> pd.DataFrame:
    """Historial completo y ordenado de `clasificador` estrictamente anterior a `fecha`.

    Se trae el historico completo (no solo una ventana) porque el pipeline de
    features del notebook incluye una media expansiva (`expand_mean_clasificador`)
    calculada sobre todo el historico disponible de la categoria.
    """
    stmt = (
        select(
            SalesHistory.clasificador,
            SalesHistory.dia,
            SalesHistory.cantidad_vendida,
            SalesHistory.precio_medio,
        )
        .where(SalesHistory.clasificador == clasificador, SalesHistory.dia < fecha)
        .order_by(SalesHistory.dia)
    )
    result = await db.execute(stmt)
    rows = result.all()
    df = pd.DataFrame(rows, columns=HISTORY_COLUMNS)
    df["dia"] = pd.to_datetime(df["dia"])
    return df


async def get_all_history(db: AsyncSession) -> pd.DataFrame:
    """Todo el historico de ventas, de todas las categorias, ordenado por
    clasificador y dia -- fuente de datos del reentrenamiento (`app.ml.training`),
    a diferencia del CSV estatico que usa el notebook original: aqui se
    entrena con lo que realmente se ha ingerido por la app hasta el momento.
    """
    stmt = select(
        SalesHistory.clasificador,
        SalesHistory.dia,
        SalesHistory.cantidad_vendida,
        SalesHistory.precio_medio,
    ).order_by(SalesHistory.clasificador, SalesHistory.dia)
    result = await db.execute(stmt)
    rows = result.all()
    df = pd.DataFrame(rows, columns=HISTORY_COLUMNS)
    df["dia"] = pd.to_datetime(df["dia"])
    return df


async def upsert_records(
    db: AsyncSession, records: list[SalesRecordIn], valid_clasificadores: set[str]
) -> BulkUpsertResponse:
    """Inserta o actualiza (`ON CONFLICT (clasificador, dia) DO UPDATE`) un lote de registros.

    Filas con un `clasificador` fuera de `valid_clasificadores` se rechazan
    (reportadas en `errors`) sin abortar el resto del lote.
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
                "dia": record.dia,
                "cantidad_vendida": record.cantidad_vendida,
                "precio_medio": record.precio_medio,
            }
        )

    if payloads:
        stmt = pg_insert(SalesHistory)
        stmt = stmt.on_conflict_do_update(
            index_elements=["clasificador", "dia"],
            set_={
                "cantidad_vendida": stmt.excluded.cantidad_vendida,
                "precio_medio": stmt.excluded.precio_medio,
                "updated_at": func.now(),
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


async def list_history(
    db: AsyncSession,
    *,
    clasificador: str | None,
    from_date: date | None,
    to_date: date | None,
    page: int,
    page_size: int,
) -> tuple[list[SalesHistory], int]:
    """Lista paginada del historico, con filtros opcionales."""
    filters = []
    if clasificador is not None:
        filters.append(SalesHistory.clasificador == clasificador)
    if from_date is not None:
        filters.append(SalesHistory.dia >= from_date)
    if to_date is not None:
        filters.append(SalesHistory.dia <= to_date)

    total = (
        await db.execute(select(func.count()).select_from(SalesHistory).where(*filters))
    ).scalar_one()

    stmt = (
        select(SalesHistory)
        .where(*filters)
        .order_by(SalesHistory.dia.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows), total
