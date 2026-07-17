"""Rutas de generacion de reportes PDF (semanal/mensual). Solo administradores."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_ml_registry, require_admin
from app.core.config import Settings, get_settings
from app.db.models.user import User
from app.ml.registry import MLModelRegistry
from app.reports.pdf_generator import generate_report

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(require_admin)])


async def _report_response(
    db: AsyncSession,
    registry: MLModelRegistry,
    settings: Settings,
    user: User,
    horizonte: str,
    fecha_inicio: date,
    clasificadores: list[str] | None,
    filename_prefix: str,
) -> Response:
    pdf_bytes = await generate_report(
        db,
        registry,
        settings,
        horizonte=horizonte,
        fecha_inicio=fecha_inicio,
        user_id=user.id,
        clasificadores=clasificadores,
    )
    filename = f"{filename_prefix}_{fecha_inicio:%Y%m%d}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/weekly",
    summary="Reporte PDF semanal de reabastecimiento",
    description="Genera un PDF (7 dias proyectados desde `fecha_inicio`) con demanda "
    "proyectada por categoria, tabla de prioridades de reabastecimiento, costos y un "
    "resumen ejecutivo generado por LLM. `clasificadores` es opcional y filtra las "
    "categorias incluidas (por defecto, todas).",
    responses={200: {"content": {"application/pdf": {}}, "description": "Archivo PDF."}},
)
async def weekly_report(
    fecha_inicio: date = Query(..., description="Primer dia del periodo a proyectar."),
    clasificadores: list[str] | None = Query(
        default=None, description="Subconjunto de categorias a incluir (repetir el parametro)."
    ),
    db: AsyncSession = Depends(get_db),
    registry: MLModelRegistry = Depends(get_ml_registry),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
) -> Response:
    return await _report_response(
        db, registry, settings, user, "week", fecha_inicio, clasificadores, "reporte_semanal"
    )


@router.get(
    "/monthly",
    summary="Reporte PDF mensual de reabastecimiento",
    description="Igual que `/weekly` pero proyectando 30 dias desde `fecha_inicio`.",
    responses={200: {"content": {"application/pdf": {}}, "description": "Archivo PDF."}},
)
async def monthly_report(
    fecha_inicio: date = Query(..., description="Primer dia del periodo a proyectar."),
    clasificadores: list[str] | None = Query(
        default=None, description="Subconjunto de categorias a incluir (repetir el parametro)."
    ),
    db: AsyncSession = Depends(get_db),
    registry: MLModelRegistry = Depends(get_ml_registry),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
) -> Response:
    return await _report_response(
        db, registry, settings, user, "month", fecha_inicio, clasificadores, "reporte_mensual"
    )
