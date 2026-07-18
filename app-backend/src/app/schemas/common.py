"""Schemas Pydantic compartidos por multiples endpoints."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Cuerpo del error normalizado que devuelven todos los exception handlers."""

    code: str = Field(..., description="Codigo de error legible por maquina, ej. NOT_FOUND.")
    message: str = Field(..., description="Mensaje de error legible por humanos.")
    details: dict[str, Any] | None = Field(
        default=None, description="Detalles adicionales del error, si aplica."
    )


class ErrorResponse(BaseModel):
    """Envoltorio de error devuelto por la API: `{"error": {...}}`."""

    error: ErrorDetail


class PaginationMeta(BaseModel):
    """Metadatos de paginacion."""

    page: int = Field(..., ge=1, description="Numero de pagina actual (1-indexado).")
    page_size: int = Field(..., ge=1, description="Cantidad de elementos por pagina.")
    total_items: int = Field(..., ge=0, description="Total de elementos disponibles.")
    total_pages: int = Field(..., ge=0, description="Total de paginas disponibles.")


class PaginatedResponse(BaseModel, Generic[T]):
    """Respuesta paginada generica."""

    items: list[T]
    meta: PaginationMeta
