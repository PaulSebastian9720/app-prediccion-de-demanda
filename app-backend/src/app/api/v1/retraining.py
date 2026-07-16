"""Rutas de reentrenamiento del modelo y versionado (activo/historial de versiones)."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_ml_registry, require_admin
from app.core.constants import RetrainingJobStatus
from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.retraining_job import RetrainingJob
from app.db.models.user import User
from app.ml.registry import MLModelRegistry
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.model_version import ModelVersionResponse
from app.schemas.retraining import RetrainingJobResponse
from app.services import retraining_service

router = APIRouter(prefix="/retraining", tags=["retraining"], dependencies=[Depends(require_admin)])


@router.post(
    "/trigger",
    response_model=RetrainingJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Disparar un reentrenamiento",
    description="Reentrena desde cero (RandomizedSearchCV + TimeSeriesSplit sobre TODO el "
    "historial de `sales_history`, no un CSV fijo) en background -- responde de inmediato "
    "con el job en `pending`; consultar su estado con `GET /retraining/jobs/{id}`. `409` si "
    "ya hay un reentrenamiento en curso.",
)
async def trigger_retraining(
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    registry: MLModelRegistry = Depends(get_ml_registry),
) -> RetrainingJobResponse:
    if await retraining_service.has_active_job(db):
        raise ConflictError("Ya hay un reentrenamiento en curso.")

    job = RetrainingJob(status=RetrainingJobStatus.PENDING, triggered_by_user_id=user.id)
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # El trabajo pesado (CPU-bound) corre con `asyncio.to_thread` dentro de
    # `run_retraining_job` -- `BackgroundTasks` solo lo programa para despues
    # de responder, sin bloquear al cliente ni introducir una cola nueva.
    # `registry` viene de `Depends(get_ml_registry)` (no de `app.state`
    # directo) para que los tests puedan overridear la dependencia igual que
    # en el resto de la app.
    background_tasks.add_task(
        retraining_service.run_retraining_job,
        job.id,
        request.app.state.session_factory,
        request.app.state.settings,
        registry,
    )
    return RetrainingJobResponse.model_validate(job)


@router.get(
    "/jobs",
    response_model=PaginatedResponse[RetrainingJobResponse],
    summary="Historial de jobs de reentrenamiento",
)
async def list_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[RetrainingJobResponse]:
    rows, total = await retraining_service.list_jobs(db, page=page, page_size=page_size)
    total_pages = (total + page_size - 1) // page_size if total else 0
    return PaginatedResponse(
        items=[RetrainingJobResponse.model_validate(row) for row in rows],
        meta=PaginationMeta(
            page=page, page_size=page_size, total_items=total, total_pages=total_pages
        ),
    )


@router.get(
    "/jobs/{job_id}",
    response_model=RetrainingJobResponse,
    summary="Estado de un job de reentrenamiento",
)
async def get_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> RetrainingJobResponse:
    job = await db.get(RetrainingJob, job_id)
    if job is None:
        raise NotFoundError(f"No existe un job de reentrenamiento con id '{job_id}'.")
    return RetrainingJobResponse.model_validate(job)


@router.get(
    "/versions",
    response_model=list[ModelVersionResponse],
    summary="Historial de versiones del modelo",
    description="Todas las versiones guardadas, mas recientes primero, con sus metricas "
    "(MAE/RMSE/R2 de validacion y prueba) y cual esta activa en este momento.",
)
async def list_versions(db: AsyncSession = Depends(get_db)) -> list[ModelVersionResponse]:
    rows = await retraining_service.list_versions(db)
    return [ModelVersionResponse.model_validate(row) for row in rows]


@router.post(
    "/versions/{version_id}/activate",
    response_model=ModelVersionResponse,
    summary="Activar una version del modelo manualmente",
    description="Cambia cual version sirve las predicciones, con recarga en caliente "
    "(sin reiniciar el servidor). Util para volver a una version anterior, o para activar "
    "a mano una version que el sistema guardo pero no activo automaticamente (porque su MAE "
    "de prueba no mejoraba al de la version activa en ese momento).",
)
async def activate_version(
    version_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    registry: MLModelRegistry = Depends(get_ml_registry),
) -> ModelVersionResponse:
    version = await retraining_service.activate_version(
        db, registry, request.app.state.settings, version_id
    )
    return ModelVersionResponse.model_validate(version)
