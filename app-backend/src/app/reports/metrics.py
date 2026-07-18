"""Calculo de metricas de negocio por categoria para el reporte de reabastecimiento.

Funciones puras (sin I/O): reciben la demanda ya proyectada (de
`prediction_service.predict_range`) y las filas de `products`/`inventory_stock`
ya cargadas, y devuelven las metricas derivadas.
"""

from dataclasses import dataclass
from datetime import date

from app.db.models.inventory_stock import InventoryStock
from app.db.models.product import Product

PRIORIDAD_ALTA = "Alta"
PRIORIDAD_MEDIA = "Media"
PRIORIDAD_BAJA = "Baja"

_ORDEN_PRIORIDAD = {PRIORIDAD_ALTA: 0, PRIORIDAD_MEDIA: 1, PRIORIDAD_BAJA: 2}


@dataclass
class CategoryReportRow:
    """Fila de la tabla de prioridades de un reporte, una por categoria."""

    clasificador: str
    nombre_display: str
    demanda_proyectada: int
    stock_actual: float
    stock_minimo: float
    precio_venta: float
    costo_reposicion_unitario: float
    dias_inventario_restante: float | None
    unidades_en_riesgo: float
    costo_oportunidad_quiebre: float
    unidades_a_reponer: float
    costo_reposicion_total: float
    prioridad: str
    predicciones_diarias: list[tuple[date, int]]


def _clasificar_prioridad(dias_inventario_restante: float | None, dias_periodo: int) -> str:
    """Alta si el stock no alcanza ni la mitad del periodo; Media si no alcanza
    todo el periodo; Baja si alcanza y sobra (o no hay demanda proyectada)."""
    if dias_inventario_restante is None:
        return PRIORIDAD_BAJA
    if dias_inventario_restante <= dias_periodo * 0.5:
        return PRIORIDAD_ALTA
    if dias_inventario_restante <= dias_periodo:
        return PRIORIDAD_MEDIA
    return PRIORIDAD_BAJA


def build_category_row(
    *,
    clasificador: str,
    demanda_proyectada: int,
    dias_periodo: int,
    product: Product,
    stock: InventoryStock,
    predicciones_diarias: list[tuple[date, int]],
) -> CategoryReportRow:
    """Calcula las 3 metricas de negocio del reporte para una categoria.

    - dias_inventario_restante = stock_actual / demanda_diaria_proyectada
    - costo_oportunidad_quiebre = max(0, demanda - stock_actual) * precio_venta
    - costo_reposicion_total = max(0, demanda + stock_minimo - stock_actual) * costo_reposicion
    """
    demanda_diaria = demanda_proyectada / dias_periodo if dias_periodo else 0.0
    dias_inventario_restante = stock.stock_actual / demanda_diaria if demanda_diaria > 0 else None

    unidades_en_riesgo = max(0.0, demanda_proyectada - stock.stock_actual)
    costo_oportunidad_quiebre = unidades_en_riesgo * product.precio_venta

    unidades_a_reponer = max(0.0, demanda_proyectada + stock.stock_minimo - stock.stock_actual)
    costo_reposicion_total = unidades_a_reponer * product.costo_reposicion

    prioridad = _clasificar_prioridad(dias_inventario_restante, dias_periodo)

    return CategoryReportRow(
        clasificador=clasificador,
        nombre_display=product.nombre_display,
        demanda_proyectada=demanda_proyectada,
        stock_actual=stock.stock_actual,
        stock_minimo=stock.stock_minimo,
        precio_venta=product.precio_venta,
        costo_reposicion_unitario=product.costo_reposicion,
        dias_inventario_restante=dias_inventario_restante,
        unidades_en_riesgo=unidades_en_riesgo,
        costo_oportunidad_quiebre=costo_oportunidad_quiebre,
        unidades_a_reponer=unidades_a_reponer,
        costo_reposicion_total=costo_reposicion_total,
        prioridad=prioridad,
        predicciones_diarias=predicciones_diarias,
    )


def build_category_narrative(row: CategoryReportRow, currency: str) -> str:
    """Texto analitico corto por categoria, construido con las metricas ya
    calculadas en `row` (sin volver a tocar la base de datos ni el LLM): una
    frase de contexto (demanda vs. stock) mas una recomendacion segun
    prioridad."""
    if row.dias_inventario_restante is not None:
        contexto = (
            f"Se proyectan {row.demanda_proyectada} u. de demanda en el periodo, frente a un "
            f"stock actual de {row.stock_actual:.0f} u.: el inventario cubre aproximadamente "
            f"{row.dias_inventario_restante:.1f} dias al ritmo de venta proyectado."
        )
    else:
        contexto = (
            f"No se proyecta demanda para esta categoria en el periodo (stock actual de "
            f"{row.stock_actual:.0f} u.), por lo que no aplica un calculo de dias de cobertura."
        )

    if row.prioridad == PRIORIDAD_ALTA:
        recomendacion = (
            f"Esta en riesgo de quiebre de stock: se recomienda reponer cuanto antes "
            f"({row.unidades_a_reponer:.0f} u., inversion aproximada de "
            f"{currency}{row.costo_reposicion_total:,.2f})."
        )
    elif row.prioridad == PRIORIDAD_MEDIA:
        recomendacion = (
            f"El margen es ajustado: conviene planificar la reposicion pronto "
            f"({row.unidades_a_reponer:.0f} u. sugeridas, {currency}"
            f"{row.costo_reposicion_total:,.2f})."
        )
    else:
        recomendacion = "El inventario es suficiente para cubrir la demanda proyectada sin acciones inmediatas."

    return f"{contexto} {recomendacion}"


def sort_by_priority(rows: list[CategoryReportRow]) -> list[CategoryReportRow]:
    """Ordena las filas Alta -> Media -> Baja (y por demanda descendente dentro de cada grupo)."""
    return sorted(
        rows, key=lambda r: (_ORDEN_PRIORIDAD.get(r.prioridad, 99), -r.demanda_proyectada)
    )
