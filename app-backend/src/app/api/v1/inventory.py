"""Rutas de consulta y actualizacion del inventario/stock actual por categoria."""

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_ml_registry, require_admin
from app.core.exceptions import InvalidFileError
from app.ml.registry import MLModelRegistry
from app.schemas.inventory import InventoryStockResponse, InventoryUpsertBatchRequest
from app.schemas.sales_history import BulkUpsertResponse
from app.services import inventory_service
from app.utils.file_parsers import FileParsingError, parse_inventory_upload

router = APIRouter(prefix="/inventory", tags=["inventory"])


def _build_template_csv(clasificadores: list[str], stock_actual: dict[str, InventoryStockResponse]) -> str:
    """Header + una fila por cada `clasificador` valido, con su stock ACTUAL
    ya cargado (si existe) en vez de ceros -- la plantilla sirve para
    actualizar, asi que el usuario solo edita lo que cambio, no reescribe
    todo desde cero."""
    lineas = ["clasificador,stock_actual,stock_minimo"]
    for clasificador in clasificadores:
        fila = stock_actual.get(clasificador)
        actual = fila.stock_actual if fila else 0
        minimo = fila.stock_minimo if fila else 0
        lineas.append(f"{clasificador},{actual},{minimo}")
    return "\n".join(lineas) + "\n"


@router.get(
    "/",
    response_model=list[InventoryStockResponse],
    summary="Consultar stock actual",
    dependencies=[Depends(get_current_user)],
)
async def list_stock(db: AsyncSession = Depends(get_db)) -> list[InventoryStockResponse]:
    rows = await inventory_service.list_stock(db)
    return [InventoryStockResponse.model_validate(r) for r in rows]


@router.post(
    "/",
    response_model=BulkUpsertResponse,
    summary="Cargar/actualizar stock actual (JSON)",
    description="Upsert por categoria (`ON CONFLICT (clasificador) DO UPDATE`). Solo "
    "administradores. Filas con un `clasificador` fuera de las categorias reconocidas por "
    "el modelo se rechazan (reportadas en `errors`) sin abortar el resto del lote.",
    dependencies=[Depends(require_admin)],
)
async def upsert_stock(
    payload: InventoryUpsertBatchRequest,
    db: AsyncSession = Depends(get_db),
    registry: MLModelRegistry = Depends(get_ml_registry),
) -> BulkUpsertResponse:
    return await inventory_service.upsert_stock(
        db, payload.registros, set(registry.clasificadores_validos)
    )


@router.post(
    "/upload",
    response_model=BulkUpsertResponse,
    summary="Cargar/actualizar stock actual (archivo CSV/XLSX)",
    description="Mismo comportamiento que el endpoint JSON, pero recibe un archivo `.csv` o "
    "`.xlsx` con las columnas `clasificador,stock_actual,stock_minimo`. `stock_actual`/"
    "`stock_minimo` deben ser enteros no-negativos -- un valor decimal o negativo se "
    "reporta como fila rechazada, no aborta el archivo completo.",
    responses={422: {"description": "Archivo con formato invalido o columnas faltantes."}},
    dependencies=[Depends(require_admin)],
)
async def upload_stock_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    registry: MLModelRegistry = Depends(get_ml_registry),
) -> BulkUpsertResponse:
    content = await file.read()
    try:
        records, parse_errors = parse_inventory_upload(file.filename or "archivo", content)
    except FileParsingError as exc:
        raise InvalidFileError(str(exc)) from exc

    result = await inventory_service.upsert_stock(
        db, records, set(registry.clasificadores_validos)
    )
    return BulkUpsertResponse(
        rows_received=result.rows_received + len(parse_errors),
        rows_upserted=result.rows_upserted,
        rows_rejected=result.rows_rejected + len(parse_errors),
        errors=[*parse_errors, *result.errors],
    )


@router.get(
    "/upload/template",
    summary="Descargar plantilla CSV para carga de stock",
    dependencies=[Depends(require_admin)],
)
async def download_stock_template(
    db: AsyncSession = Depends(get_db),
    registry: MLModelRegistry = Depends(get_ml_registry),
) -> Response:
    stock_map = {row.clasificador: InventoryStockResponse.model_validate(row) for row in await inventory_service.list_stock(db)}
    return Response(
        content=_build_template_csv(registry.clasificadores_validos, stock_map),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="plantilla_stock.csv"'},
    )
