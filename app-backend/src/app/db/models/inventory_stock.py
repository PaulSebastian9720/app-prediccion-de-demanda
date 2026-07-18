"""Modelo de inventario/stock fisico actual por categoria.

Concepto distinto de `sales_history` (que es demanda/ventas historicas): esto
representa cuanto hay HOY en bodega, dato que el modelo de forecasting no conoce
y que hace falta para calcular prioridad de reabastecimiento.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InventoryStock(Base):
    """Stock actual y stock minimo (umbral de seguridad) de una categoria.

    Ambas columnas son enteras y no-negativas a proposito: el stock fisico
    nunca es fraccionario en este negocio (ver migracion que redondea los
    valores decimales que existian antes de este cambio).
    """

    __tablename__ = "inventory_stock"

    clasificador: Mapped[str] = mapped_column(String(64), primary_key=True)
    stock_actual: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_minimo: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
