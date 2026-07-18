"""Modelo de catalogo de productos: precio de venta y costo de reposicion por categoria."""

from datetime import datetime

from sqlalchemy import DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Product(Base):
    """Precio/costo de referencia de una categoria (`clasificador`).

    `precio_venta` se siembra como el promedio historico real de
    `sales_history.precio_medio` para esa categoria (no un numero arbitrario);
    `costo_reposicion` se deriva de ahi con un margen tipico. Ambos son
    editables despues via `PATCH /products/{clasificador}`.
    """

    __tablename__ = "products"

    clasificador: Mapped[str] = mapped_column(String(64), primary_key=True)
    nombre_display: Mapped[str] = mapped_column(String(255), nullable=False)
    precio_venta: Mapped[float] = mapped_column(Float, nullable=False)
    costo_reposicion: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
