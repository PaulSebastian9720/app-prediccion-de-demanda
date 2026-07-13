"""Modelo del historico diario de ventas por categoria, usado para construir features de lag."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SalesHistory(Base):
    """Una fila = ventas de una categoria (`clasificador`) en un dia dado.

    `ingested_at`/`updated_at` son metadatos de auditoria (no de negocio): le
    permiten a un futuro job de reentrenamiento preguntar que filas son nuevas
    desde el ultimo entrenamiento (`metadata_modelo.json.fecha_entrenamiento`)
    sin depender de `dia`, que es la fecha de la venta, no la de carga.
    """

    __tablename__ = "sales_history"
    __table_args__ = (
        UniqueConstraint("clasificador", "dia", name="uq_sales_history_clasificador_dia"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    clasificador: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    dia: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    cantidad_vendida: Mapped[float] = mapped_column(Float, nullable=False)
    precio_medio: Mapped[float] = mapped_column(Float, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
