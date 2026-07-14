"""Rutas de consulta de logs (requests, inferencias, eventos de pipeline). Solo administradores."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.core.exceptions import NotFoundError
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.logs import InferenceLogResponse, PipelineEventResponse, RequestLogResponse
from app.services import log_service

router = APIRouter(prefix="/logs", tags=["logs"], dependencies=[Depends(require_admin)])


@router.get(
    "/requests",
    response_model=PaginatedResponse[RequestLogResponse],
    summary="Consultar logs de requests HTTP",
    description="Auditoria general: metodo, ruta, status, duracion, usuario e IP de cada request.",
)
async def list_request_logs(
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
    status_code: int | None = Query(default=None),
    user_id: uuid.UUID | None = Query(default=None),
    path: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[RequestLogResponse]:
    rows, total = await log_service.list_request_logs(
        db,
        from_date=from_date,
        to_date=to_date,
        status_code=status_code,
        user_id=user_id,
        path=path,
        page=page,
        page_size=page_size,
    )
    total_pages = (total + page_size - 1) // page_size if total else 0
    return PaginatedResponse(
        items=[RequestLogResponse.model_validate(r) for r in rows],
        meta=PaginationMeta(
            page=page, page_size=page_size, total_items=total, total_pages=total_pages
        ),
    )


@router.get(
    "/inferences",
    response_model=PaginatedResponse[InferenceLogResponse],
    summary="Consultar logs de inferencias (predicciones)",
)
async def list_inference_logs(
    clasificador: str | None = Query(default=None),
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[InferenceLogResponse]:
    rows, total = await log_service.list_inference_logs(
        db,
        clasificador=clasificador,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )
    total_pages = (total + page_size - 1) // page_size if total else 0
    return PaginatedResponse(
        items=[InferenceLogResponse.model_validate(r) for r in rows],
        meta=PaginationMeta(
            page=page, page_size=page_size, total_items=total, total_pages=total_pages
        ),
    )


@router.get(
    "/inferences/{inference_log_id}/events",
    response_model=list[PipelineEventResponse],
    summary="Etapas del pipeline de una prediccion especifica",
    description="Trazabilidad granular de una prediccion: en que parte del pipeline se "
    "encontraba (obtencion de historial, construccion de features, codificacion, "
    "inferencia del modelo, postproceso, o cada dia iterado en predicciones de rango), "
    "con la duracion de cada etapa.",
    responses={404: {"description": "No existe una inferencia con ese id."}},
)
async def get_inference_events(
    inference_log_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[PipelineEventResponse]:
    inference_log = await log_service.get_inference_log_with_events(db, inference_log_id)
    if inference_log is None:
        raise NotFoundError(f"No existe una inferencia con id '{inference_log_id}'.")
    return [PipelineEventResponse.model_validate(e) for e in inference_log.events]
