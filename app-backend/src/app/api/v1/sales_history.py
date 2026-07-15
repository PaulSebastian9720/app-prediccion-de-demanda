"""Rutas de ingesta y consulta del historico de ventas (solo administradores)."""

from datetime import date

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_ml_registry, require_admin
from app.core.exceptions import InvalidFileError
from app.ml.registry import MLModelRegistry
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.sales_history import (
    BulkUpsertResponse,
    SalesHistoryRecordResponse,
    SalesHistoryUploadRequest,
)
from app.services import sales_history_service
from app.utils.file_parsers import FileParsingError, parse_upload

router = APIRouter(
    prefix="/sales-history", tags=["sales-history"], dependencies=[Depends(require_admin)]
)


def _build_template_csv(clasificadores: list[str]) -> str:
    """Header + una fila de ejemplo por cada `clasificador` valido -- asi la
    plantilla ya muestra los nombres EXACTOS que el modelo reconoce, en vez
    de dejar que el usuario los adivine o los copie de otro lado."""
    lineas = ["clasificador,dia,cantidad_vendida,precio_medio"]
    hoy = date.today().isoformat()
    lineas.extend(f"{clasificador},{hoy},0,0.0" for clasificador in clasificadores)
    return "\n".join(lineas) + "\n"


@router.post(
    "/",
    response_model=BulkUpsertResponse,
    summary="Cargar/actualizar ventas (JSON)",
    description="Inserta o actualiza (upsert por `clasificador`+`dia`) un lote de registros. "
    "No se aceptan categorias fuera de las reconocidas por el modelo (`GET /predictions/clasificadores`).",
)
async def upload_json(
    payload: SalesHistoryUploadRequest,
    db: AsyncSession = Depends(get_db),
    registry: MLModelRegistry = Depends(get_ml_registry),
) -> BulkUpsertResponse:
    return await sales_history_service.upsert_records(
        db, payload.registros, set(registry.clasificadores_validos)
    )


@router.post(
    "/upload",
    response_model=BulkUpsertResponse,
    summary="Cargar/actualizar ventas (archivo CSV/XLSX/XML)",
    description="Mismo comportamiento que el endpoint JSON, pero recibe un archivo `.csv`, "
    "`.xlsx` o `.xml` con las columnas `clasificador,dia,cantidad_vendida,precio_medio`. "
    "El formato se detecta por la extension del archivo.",
    responses={422: {"description": "Archivo con formato invalido o columnas faltantes."}},
)
async def upload_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    registry: MLModelRegistry = Depends(get_ml_registry),
) -> BulkUpsertResponse:
    content = await file.read()
    try:
        records, parse_errors = parse_upload(file.filename or "archivo", content)
    except FileParsingError as exc:
        raise InvalidFileError(str(exc)) from exc

    result = await sales_history_service.upsert_records(
        db, records, set(registry.clasificadores_validos)
    )
    return BulkUpsertResponse(
        rows_received=result.rows_received + len(parse_errors),
        rows_upserted=result.rows_upserted,
        rows_rejected=result.rows_rejected + len(parse_errors),
        errors=[*parse_errors, *result.errors],
    )


@router.get(
    "/template",
    summary="Descargar plantilla CSV para carga de ventas",
)
async def download_sales_template(
    registry: MLModelRegistry = Depends(get_ml_registry),
) -> Response:
    return Response(
        content=_build_template_csv(registry.clasificadores_validos),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="plantilla_ventas.csv"'},
    )


@router.get(
    "/",
    response_model=PaginatedResponse[SalesHistoryRecordResponse],
    summary="Consultar historico cargado",
    description="Util para verificar que datos sembrados/actualizados existen en `sales_history`.",
)
async def list_history(
    clasificador: str | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[SalesHistoryRecordResponse]:
    rows, total = await sales_history_service.list_history(
        db,
        clasificador=clasificador,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )
    total_pages = (total + page_size - 1) // page_size if total else 0
    return PaginatedResponse(
        items=[SalesHistoryRecordResponse.model_validate(r, from_attributes=True) for r in rows],
        meta=PaginationMeta(
            page=page, page_size=page_size, total_items=total, total_pages=total_pages
        ),
    )
