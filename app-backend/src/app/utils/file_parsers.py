"""Parsers de archivos de ingesta del historico de ventas (CSV / XLSX / XML).

Funciones puras basadas en `pandas`: reciben bytes crudos y devuelven
registros validados con Pydantic, sin tocar la base de datos.
"""

import io
from pathlib import Path

import pandas as pd
from pydantic import ValidationError

from app.schemas.inventory import InventoryStockUpsertRequest
from app.schemas.sales_history import RowError, SalesRecordIn

REQUIRED_COLUMNS = {"clasificador", "dia", "cantidad_vendida", "precio_medio"}
INVENTORY_REQUIRED_COLUMNS = {"clasificador", "stock_actual", "stock_minimo"}


class FileParsingError(Exception):
    """Error irrecuperable al parsear el archivo completo (formato o columnas invalidas)."""


def _dataframe_to_records(df: pd.DataFrame) -> tuple[list[SalesRecordIn], list[RowError]]:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise FileParsingError(f"Faltan columnas requeridas: {sorted(missing)}")

    records: list[SalesRecordIn] = []
    errors: list[RowError] = []
    for idx, row in enumerate(df.itertuples(index=False)):
        try:
            records.append(
                SalesRecordIn(
                    clasificador=str(row.clasificador),
                    dia=row.dia,
                    cantidad_vendida=row.cantidad_vendida,
                    precio_medio=row.precio_medio,
                )
            )
        except ValidationError as exc:
            errors.append(RowError(row=idx, reason=exc.errors()[0]["msg"]))
    return records, errors


def parse_csv(content: bytes) -> tuple[list[SalesRecordIn], list[RowError]]:
    df = pd.read_csv(io.BytesIO(content))
    return _dataframe_to_records(df)


def parse_xlsx(content: bytes) -> tuple[list[SalesRecordIn], list[RowError]]:
    df = pd.read_excel(io.BytesIO(content))
    return _dataframe_to_records(df)


def parse_xml(content: bytes) -> tuple[list[SalesRecordIn], list[RowError]]:
    df = pd.read_xml(io.BytesIO(content))
    return _dataframe_to_records(df)


_PARSERS_BY_EXTENSION = {
    ".csv": parse_csv,
    ".xlsx": parse_xlsx,
    ".xml": parse_xml,
}


def parse_upload(filename: str, content: bytes) -> tuple[list[SalesRecordIn], list[RowError]]:
    """Detecta el formato por extension y delega al parser correspondiente."""
    extension = Path(filename).suffix.lower()
    parser = _PARSERS_BY_EXTENSION.get(extension)
    if parser is None:
        raise FileParsingError(
            f"Formato de archivo no soportado: '{extension}'. Usa .csv, .xlsx o .xml."
        )
    return parser(content)


def _dataframe_to_inventory_records(
    df: pd.DataFrame,
) -> tuple[list[InventoryStockUpsertRequest], list[RowError]]:
    missing = INVENTORY_REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise FileParsingError(f"Faltan columnas requeridas: {sorted(missing)}")

    records: list[InventoryStockUpsertRequest] = []
    errors: list[RowError] = []
    for idx, row in enumerate(df.itertuples(index=False)):
        try:
            records.append(
                InventoryStockUpsertRequest(
                    clasificador=str(row.clasificador),
                    stock_actual=row.stock_actual,
                    stock_minimo=row.stock_minimo,
                )
            )
        except ValidationError as exc:
            errors.append(RowError(row=idx, reason=exc.errors()[0]["msg"]))
    return records, errors


def parse_inventory_csv(content: bytes) -> tuple[list[InventoryStockUpsertRequest], list[RowError]]:
    df = pd.read_csv(io.BytesIO(content))
    return _dataframe_to_inventory_records(df)


def parse_inventory_xlsx(content: bytes) -> tuple[list[InventoryStockUpsertRequest], list[RowError]]:
    df = pd.read_excel(io.BytesIO(content))
    return _dataframe_to_inventory_records(df)


_INVENTORY_PARSERS_BY_EXTENSION = {
    ".csv": parse_inventory_csv,
    ".xlsx": parse_inventory_xlsx,
}


def parse_inventory_upload(
    filename: str, content: bytes
) -> tuple[list[InventoryStockUpsertRequest], list[RowError]]:
    """Detecta el formato por extension y delega al parser correspondiente.

    Solo CSV/XLSX (a diferencia de `parse_upload`, que ademas soporta XML):
    no hay ningun caso de uso real hoy para stock en XML."""
    extension = Path(filename).suffix.lower()
    parser = _INVENTORY_PARSERS_BY_EXTENSION.get(extension)
    if parser is None:
        raise FileParsingError(
            f"Formato de archivo no soportado: '{extension}'. Usa .csv o .xlsx."
        )
    return parser(content)
