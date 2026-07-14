"""Consulta de logs (requests, inferencias, eventos de pipeline) y metricas operacionales."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.db.models.inference_log import InferenceLog
from app.db.models.request_log import RequestLog
from app.schemas.metrics import ServiceMetricsResponse

logger = logging.getLogger(__name__)


async def create_request_log(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    user_id: uuid.UUID | None,
    ip_address: str,
    user_agent: str | None,
) -> None:
    """Persiste un `RequestLog`. Invocado como `BackgroundTask` tras enviar la
    respuesta al cliente, con su propia sesion (la del request ya se cerro).
    """
    async with session_factory() as db:
        try:
            db.add(
                RequestLog(
                    id=uuid.uuid4(),
                    method=method,
                    path=path,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
            )
            await db.commit()
        except Exception:
            await db.rollback()
            logger.warning("No se pudo persistir request_log", exc_info=True)


async def list_request_logs(
    db: AsyncSession,
    *,
    from_date: datetime | None,
    to_date: datetime | None,
    status_code: int | None,
    user_id: uuid.UUID | None,
    path: str | None,
    page: int,
    page_size: int,
) -> tuple[list[RequestLog], int]:
    filters = []
    if from_date is not None:
        filters.append(RequestLog.created_at >= from_date)
    if to_date is not None:
        filters.append(RequestLog.created_at <= to_date)
    if status_code is not None:
        filters.append(RequestLog.status_code == status_code)
    if user_id is not None:
        filters.append(RequestLog.user_id == user_id)
    if path is not None:
        filters.append(RequestLog.path.ilike(f"%{path}%"))

    total = (
        await db.execute(select(func.count()).select_from(RequestLog).where(*filters))
    ).scalar_one()
    stmt = (
        select(RequestLog)
        .where(*filters)
        .order_by(RequestLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows), total


async def list_inference_logs(
    db: AsyncSession,
    *,
    clasificador: str | None,
    from_date: datetime | None,
    to_date: datetime | None,
    page: int,
    page_size: int,
) -> tuple[list[InferenceLog], int]:
    filters = []
    if clasificador is not None:
        filters.append(InferenceLog.clasificador == clasificador)
    if from_date is not None:
        filters.append(InferenceLog.created_at >= from_date)
    if to_date is not None:
        filters.append(InferenceLog.created_at <= to_date)

    total = (
        await db.execute(select(func.count()).select_from(InferenceLog).where(*filters))
    ).scalar_one()
    stmt = (
        select(InferenceLog)
        .where(*filters)
        .order_by(InferenceLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows), total


async def get_inference_log_with_events(
    db: AsyncSession, inference_log_id: uuid.UUID
) -> InferenceLog | None:
    stmt = (
        select(InferenceLog)
        .options(selectinload(InferenceLog.events))
        .where(InferenceLog.id == inference_log_id)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_service_metrics(db: AsyncSession) -> ServiceMetricsResponse:
    since = datetime.now(UTC) - timedelta(hours=24)

    total_requests = (
        await db.execute(
            select(func.count()).select_from(RequestLog).where(RequestLog.created_at >= since)
        )
    ).scalar_one()
    total_predictions = (
        await db.execute(
            select(func.count()).select_from(InferenceLog).where(InferenceLog.created_at >= since)
        )
    ).scalar_one()
    avg_latency = (
        await db.execute(
            select(func.avg(RequestLog.duration_ms)).where(RequestLog.created_at >= since)
        )
    ).scalar_one()
    error_count = (
        await db.execute(
            select(func.count())
            .select_from(RequestLog)
            .where(RequestLog.created_at >= since, RequestLog.status_code >= 400)
        )
    ).scalar_one()

    error_rate = (error_count / total_requests) if total_requests else 0.0

    return ServiceMetricsResponse(
        total_requests_24h=total_requests,
        total_predictions_24h=total_predictions,
        avg_latency_ms_24h=float(avg_latency or 0.0),
        error_rate_24h=round(error_rate, 4),
    )
