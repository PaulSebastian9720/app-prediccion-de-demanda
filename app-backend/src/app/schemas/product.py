"""Schemas del catalogo de productos (precio de venta / costo de reposicion)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProductResponse(BaseModel):
    """Precio/costo de referencia de una categoria."""

    model_config = ConfigDict(from_attributes=True)

    clasificador: str
    nombre_display: str
    precio_venta: float
    costo_reposicion: float
    updated_at: datetime


class ProductUpdateRequest(BaseModel):
    """Campos editables del catalogo, todos opcionales (actualizacion parcial)."""

    nombre_display: str | None = Field(default=None, max_length=255)
    precio_venta: float | None = Field(default=None, ge=0)
    costo_reposicion: float | None = Field(default=None, ge=0)
