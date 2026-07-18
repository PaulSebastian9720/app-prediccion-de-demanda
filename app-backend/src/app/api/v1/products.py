"""Rutas de consulta y administracion del catalogo de productos (precio/costo)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_admin
from app.schemas.product import ProductResponse, ProductUpdateRequest
from app.services import product_service

router = APIRouter(prefix="/products", tags=["products"])


@router.get(
    "/",
    response_model=list[ProductResponse],
    summary="Listar catalogo de productos",
    description="Precio de venta y costo de reposicion por categoria (usados tambien por "
    "los reportes PDF). Disponible para cualquier usuario autenticado.",
    dependencies=[Depends(get_current_user)],
)
async def list_products(db: AsyncSession = Depends(get_db)) -> list[ProductResponse]:
    products = await product_service.list_products(db)
    return [ProductResponse.model_validate(p) for p in products]


@router.patch(
    "/{clasificador}",
    response_model=ProductResponse,
    summary="Actualizar precio de venta / costo de reposicion de una categoria",
    description="Solo administradores.",
    dependencies=[Depends(require_admin)],
)
async def update_product(
    clasificador: str, payload: ProductUpdateRequest, db: AsyncSession = Depends(get_db)
) -> ProductResponse:
    product = await product_service.update_product(db, clasificador, payload)
    return ProductResponse.model_validate(product)
