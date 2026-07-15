"""Schemas de ingesta y consulta del historico de ventas."""

from datetime import date

from pydantic import BaseModel, Field


class SalesRecordIn(BaseModel):
    """Un registro de ventas de una categoria en un dia dado (entrada de ingesta)."""

    clasificador: str = Field(..., examples=["PASEO_SUJECION"])
    dia: date = Field(..., examples=["2026-07-10"])
    cantidad_vendida: float = Field(..., ge=0, examples=[23.0])
    precio_medio: float = Field(..., ge=0, examples=[8.5])


class SalesHistoryUploadRequest(BaseModel):
    """Body JSON con un lote de registros a insertar/actualizar."""

    registros: list[SalesRecordIn] = Field(..., min_length=1)


class RowError(BaseModel):
    """Motivo de rechazo de una fila especifica de un lote de ingesta."""

    row: int = Field(..., description="Indice (0-based) de la fila rechazada.")
    reason: str


class BulkUpsertResponse(BaseModel):
    """Resultado de un upsert masivo en `sales_history`."""

    rows_received: int
    rows_upserted: int
    rows_rejected: int
    errors: list[RowError]


class SalesHistoryRecordResponse(BaseModel):
    """Registro almacenado en `sales_history`."""

    id: int
    clasificador: str
    dia: date
    cantidad_vendida: float
    precio_medio: float
