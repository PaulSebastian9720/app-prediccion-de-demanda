"""Schemas de inventario/stock actual por categoria."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InventoryStockResponse(BaseModel):
    """Stock actual y stock minimo de una categoria."""

    model_config = ConfigDict(from_attributes=True)

    clasificador: str
    stock_actual: int
    stock_minimo: int
    updated_at: datetime


class InventoryStockUpsertRequest(BaseModel):
    """Un registro de stock a insertar/actualizar.

    Enteros estrictos y no-negativos: el stock fisico nunca es fraccionario.
    """

    clasificador: str = Field(..., examples=["PASEO_SUJECION"])
    stock_actual: int = Field(..., ge=0, examples=[120])
    stock_minimo: int = Field(..., ge=0, examples=[30])


class InventoryUpsertBatchRequest(BaseModel):
    """Body JSON con un lote de registros de stock a insertar/actualizar."""

    registros: list[InventoryStockUpsertRequest] = Field(..., min_length=1)
