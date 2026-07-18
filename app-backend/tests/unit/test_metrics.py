"""Tests unitarios del calculo de metricas de negocio para el reporte PDF."""

from app.db.models.inventory_stock import InventoryStock
from app.db.models.product import Product
from app.reports.metrics import (
    PRIORIDAD_ALTA,
    PRIORIDAD_BAJA,
    PRIORIDAD_MEDIA,
    build_category_row,
    sort_by_priority,
)


def _product(precio_venta: float, costo_reposicion: float) -> Product:
    return Product(
        clasificador="TEST",
        nombre_display="Test",
        precio_venta=precio_venta,
        costo_reposicion=costo_reposicion,
    )


def _stock(stock_actual: float, stock_minimo: float) -> InventoryStock:
    return InventoryStock(clasificador="TEST", stock_actual=stock_actual, stock_minimo=stock_minimo)


def test_priority_alta_when_stock_runs_out_before_half_period() -> None:
    # demanda 140 en 7 dias -> 20/dia; stock 40 -> dura 2 dias (<= 3.5) -> Alta
    row = build_category_row(
        clasificador="TEST",
        demanda_proyectada=140,
        dias_periodo=7,
        product=_product(precio_venta=10.0, costo_reposicion=6.0),
        stock=_stock(stock_actual=40.0, stock_minimo=10.0),
        predicciones_diarias=[],
    )
    assert row.dias_inventario_restante == 2.0
    assert row.prioridad == PRIORIDAD_ALTA
    assert row.unidades_en_riesgo == 100.0
    assert row.costo_oportunidad_quiebre == 1000.0
    assert row.unidades_a_reponer == 110.0  # 140 + 10 - 40
    assert row.costo_reposicion_total == 660.0  # 110 * 6.0


def test_priority_media_when_stock_runs_out_within_period() -> None:
    # demanda 70 en 7 dias -> 10/dia; stock 50 -> dura 5 dias (entre 3.5 y 7) -> Media
    row = build_category_row(
        clasificador="TEST",
        demanda_proyectada=70,
        dias_periodo=7,
        product=_product(precio_venta=5.0, costo_reposicion=3.0),
        stock=_stock(stock_actual=50.0, stock_minimo=5.0),
        predicciones_diarias=[],
    )
    assert row.dias_inventario_restante == 5.0
    assert row.prioridad == PRIORIDAD_MEDIA


def test_priority_baja_when_stock_covers_the_whole_period() -> None:
    row = build_category_row(
        clasificador="TEST",
        demanda_proyectada=14,
        dias_periodo=7,
        product=_product(precio_venta=5.0, costo_reposicion=3.0),
        stock=_stock(stock_actual=100.0, stock_minimo=5.0),
        predicciones_diarias=[],
    )
    assert row.prioridad == PRIORIDAD_BAJA
    assert row.unidades_en_riesgo == 0.0
    assert row.costo_oportunidad_quiebre == 0.0
    assert row.unidades_a_reponer == 0.0


def test_priority_baja_when_no_demand_projected() -> None:
    row = build_category_row(
        clasificador="TEST",
        demanda_proyectada=0,
        dias_periodo=7,
        product=_product(precio_venta=5.0, costo_reposicion=3.0),
        stock=_stock(stock_actual=10.0, stock_minimo=2.0),
        predicciones_diarias=[],
    )
    assert row.dias_inventario_restante is None
    assert row.prioridad == PRIORIDAD_BAJA


def test_sort_by_priority_orders_alta_media_baja() -> None:
    alta = build_category_row(
        clasificador="A",
        demanda_proyectada=140,
        dias_periodo=7,
        product=_product(10.0, 6.0),
        stock=_stock(40.0, 10.0),
        predicciones_diarias=[],
    )
    baja = build_category_row(
        clasificador="B",
        demanda_proyectada=14,
        dias_periodo=7,
        product=_product(5.0, 3.0),
        stock=_stock(100.0, 5.0),
        predicciones_diarias=[],
    )
    media = build_category_row(
        clasificador="C",
        demanda_proyectada=70,
        dias_periodo=7,
        product=_product(5.0, 3.0),
        stock=_stock(50.0, 5.0),
        predicciones_diarias=[],
    )

    ordered = sort_by_priority([baja, alta, media])

    assert [r.clasificador for r in ordered] == ["A", "C", "B"]
