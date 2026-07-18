"""Orquesta la generacion del reporte PDF: predicciones -> metricas -> graficas -> LLM -> HTML -> PDF.

Cada categoria se predice reutilizando `prediction_service.predict_range` tal
cual (mismo pipeline instrumentado, mismos `inference_logs`/`pipeline_events`
que ya existen) — este modulo no reimplementa nada de inferencia, solo agrega
precio/costo/stock y arma el documento.
"""

import asyncio
import base64
import logging
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

import jinja2
from sqlalchemy.ext.asyncio import AsyncSession
from weasyprint import HTML

from app.core.config import Settings
from app.core.constants import PredictionHorizon
from app.core.exceptions import UnknownClassifierError
from app.db.models.report_generation_log import ReportGenerationLog
from app.ml.registry import MLModelRegistry
from app.reports import charts, summary_llm
from app.reports.metrics import (
    CategoryReportRow,
    build_category_narrative,
    build_category_row,
    sort_by_priority,
)
from app.services import inventory_service, prediction_service, product_service

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(_TEMPLATE_DIR),
    autoescape=jinja2.select_autoescape(["html", "jinja"]),
)

HORIZONTE_DIAS = {"week": 7, "month": 30}
HORIZONTE_ETIQUETA = {"week": "Semanal", "month": "Mensual"}


def _load_logo_data_uri(logo_path: Path | None) -> str | None:
    if logo_path is None or not logo_path.is_file():
        return None
    encoded = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    suffix = logo_path.suffix.lower().lstrip(".")
    mime = "svg+xml" if suffix == "svg" else suffix
    return f"data:image/{mime};base64,{encoded}"


def _resolve_clasificadores(
    registry: MLModelRegistry, clasificadores: list[str] | None
) -> list[str]:
    """Valida el filtro opcional de categorias; `None`/vacio = todas."""
    if not clasificadores:
        return list(registry.clasificadores_validos)

    validos = set(registry.clasificadores_validos)
    desconocidos = [c for c in clasificadores if c not in validos]
    if desconocidos:
        raise UnknownClassifierError(
            f"Clasificador(es) desconocido(s): {desconocidos}. Validos: {sorted(validos)}"
        )
    return clasificadores


async def _build_category_rows(
    db: AsyncSession,
    registry: MLModelRegistry,
    settings: Settings,
    *,
    dias: int,
    fecha_inicio: date,
    user_id: uuid.UUID | None,
    clasificadores: list[str] | None,
) -> list[CategoryReportRow]:
    products = await product_service.get_products_map(db)
    stock = await inventory_service.get_stock_map(db)
    seleccionadas = _resolve_clasificadores(registry, clasificadores)

    rows: list[CategoryReportRow] = []
    for clasificador in seleccionadas:
        product = products.get(clasificador)
        stock_row = stock.get(clasificador)
        if product is None or stock_row is None:
            logger.warning(
                "Sin catalogo/stock cargado para '%s'; se omite del reporte.", clasificador
            )
            continue

        # `generar_explicacion` se deja en False (default): un reporte puede
        # cubrir varias categorias, y una explicacion de periodo por cada una
        # seria exactamente el "saturar la API con LLM" que la regla de
        # negocio de este proyecto prohibe para reportes masivos.
        predicciones, total, _, _ = await prediction_service.predict_range(
            db,
            registry,
            settings,
            clasificador=clasificador,
            fecha_inicio=fecha_inicio,
            dias=dias,
            horizonte=PredictionHorizon.RANGE,
            user_id=user_id,
        )
        rows.append(
            build_category_row(
                clasificador=clasificador,
                demanda_proyectada=total,
                dias_periodo=dias,
                product=product,
                stock=stock_row,
                predicciones_diarias=predicciones,
            )
        )

    return sort_by_priority(rows)


async def _persist_report_log(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    horizonte: str,
    fecha_inicio: date,
    fecha_fin: date,
    total_alertas: int,
    duration_ms: float,
) -> None:
    try:
        db.add(
            ReportGenerationLog(
                id=uuid.uuid4(),
                user_id=user_id,
                horizonte=horizonte,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                total_alertas=total_alertas,
                duration_ms=duration_ms,
            )
        )
        await db.commit()
    except Exception:
        await db.rollback()
        logger.warning("No se pudo persistir report_generation_log", exc_info=True)


async def generate_report(
    db: AsyncSession,
    registry: MLModelRegistry,
    settings: Settings,
    *,
    horizonte: str,
    fecha_inicio: date,
    user_id: uuid.UUID | None,
    clasificadores: list[str] | None = None,
) -> bytes:
    """Genera el PDF de reabastecimiento (`horizonte` es `"week"` o `"month"`).

    `clasificadores`: subconjunto opcional de categorias a incluir (por
    defecto, todas las reconocidas por el modelo).
    """
    dias = HORIZONTE_DIAS[horizonte]
    fecha_fin = fecha_inicio + timedelta(days=dias - 1)
    horizonte_label = (
        f"{HORIZONTE_ETIQUETA[horizonte]} ({fecha_inicio:%d/%m/%Y} - {fecha_fin:%d/%m/%Y})"
    )

    start = time.perf_counter()

    rows = await _build_category_rows(
        db,
        registry,
        settings,
        dias=dias,
        fecha_inicio=fecha_inicio,
        user_id=user_id,
        clasificadores=clasificadores,
    )

    demand_chart = charts.render_demand_chart(rows)
    stock_chart = charts.render_stock_vs_demand_chart(rows)
    currency = settings.report_currency_symbol
    # Una seccion POR categoria (titulo + texto analitico + grafica propia),
    # ya agrupada por prioridad via `rows` (sort_by_priority en _build_category_rows):
    # nada de una sola grafica con las 9 series superpuestas.
    category_sections = [
        (row, build_category_narrative(row, currency), charts.render_category_trend_chart(row))
        for row in rows
    ]

    resumen = await summary_llm.generate_executive_summary(settings, rows, horizonte_label)
    logo_data_uri = _load_logo_data_uri(settings.report_logo_path)

    template = _jinja_env.get_template("report.html.jinja")
    total_alertas = sum(1 for r in rows if r.prioridad == "Alta")
    html_content = template.render(
        app_name=settings.app_name,
        logo_data_uri=logo_data_uri,
        horizonte_label=horizonte_label,
        fecha_generacion=date.today(),
        resumen=resumen,
        rows=rows,
        demand_chart=demand_chart,
        stock_chart=stock_chart,
        category_sections=category_sections,
        currency=currency,
        total_alertas=total_alertas,
        total_costo_oportunidad=sum(r.costo_oportunidad_quiebre for r in rows),
        total_costo_reposicion=sum(r.costo_reposicion_total for r in rows),
    )

    # WeasyPrint es sincrono/CPU-bound (renderiza HTML+CSS+imagenes a PDF); se
    # corre en un hilo aparte para no bloquear el event loop durante ese calculo.
    pdf_bytes = await asyncio.to_thread(HTML(string=html_content).write_pdf)

    duration_ms = (time.perf_counter() - start) * 1000
    await _persist_report_log(
        db,
        user_id=user_id,
        horizonte=horizonte,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        total_alertas=total_alertas,
        duration_ms=duration_ms,
    )

    return pdf_bytes
