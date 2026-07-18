"""Consulta y administracion del catalogo de productos (precio de venta / costo de reposicion)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.product import Product
from app.schemas.product import ProductUpdateRequest


async def list_products(db: AsyncSession) -> list[Product]:
    rows = (await db.execute(select(Product).order_by(Product.clasificador))).scalars().all()
    return list(rows)


async def get_product(db: AsyncSession, clasificador: str) -> Product:
    product = await db.get(Product, clasificador)
    if product is None:
        raise NotFoundError(f"No hay catalogo cargado para '{clasificador}'.")
    return product


async def get_products_map(db: AsyncSession) -> dict[str, Product]:
    """Todo el catalogo indexado por `clasificador` (usado por el generador de reportes)."""
    return {row.clasificador: row for row in await list_products(db)}


async def update_product(
    db: AsyncSession, clasificador: str, payload: ProductUpdateRequest
) -> Product:
    product = await get_product(db, clasificador)
    if payload.nombre_display is not None:
        product.nombre_display = payload.nombre_display
    if payload.precio_venta is not None:
        product.precio_venta = payload.precio_venta
    if payload.costo_reposicion is not None:
        product.costo_reposicion = payload.costo_reposicion
    await db.commit()
    await db.refresh(product)
    return product
