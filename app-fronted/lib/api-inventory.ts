// Ingesta real de ventas/stock: POST /sales-history/, GET+POST /inventory/,
// y subida de archivo (CSV/XLSX) + plantilla descargable para ambos. El
// reentrenamiento (jobs/versiones) vive en `lib/api-retraining.ts`.

import { apiBlob, apiJson } from "./api";
import type { IngestRow } from "./types";

export interface RowError {
  row: number;
  reason: string;
}

export interface BulkUpsertResponse {
  rows_received: number;
  rows_upserted: number;
  rows_rejected: number;
  errors: RowError[];
}

export interface InventoryStockRow {
  clasificador: string;
  stock_actual: number;
  stock_minimo: number;
  updated_at: string;
}

export async function fetchCurrentStock(): Promise<InventoryStockRow[]> {
  return apiJson<InventoryStockRow[]>("/inventory/");
}

export interface SaveIngestResult {
  ventasGuardadas: number;
  stockActualizado: number;
  erroresVentas: string[];
}

/**
 * `stockMinimoByCategoria` viene de `fetchCurrentStock()`: el backend exige
 * `stock_minimo` en cada upsert de inventario, asi que se reusa el valor ya
 * cargado para no pisarlo por accidente solo por actualizar `stock_actual`.
 */
export async function saveIngestRows(
  fecha: string,
  rows: IngestRow[],
  stockMinimoByCategoria: Record<string, number>,
): Promise<SaveIngestResult> {
  const ventas = rows.filter((r) => r.cantidadVendida !== "" && r.precioMedio !== "");
  const stock = rows.filter((r) => r.stockActual !== "");

  let ventasGuardadas = 0;
  let erroresVentas: string[] = [];

  if (ventas.length > 0) {
    const result = await apiJson<BulkUpsertResponse>("/sales-history/", {
      method: "POST",
      body: JSON.stringify({
        registros: ventas.map((r) => ({
          clasificador: r.clasificador,
          dia: fecha,
          cantidad_vendida: Number(r.cantidadVendida),
          precio_medio: Number(r.precioMedio),
        })),
      }),
    });
    ventasGuardadas = result.rows_upserted;
    erroresVentas = result.errors.map((e) => e.reason);
  }

  let stockActualizado = 0;
  if (stock.length > 0) {
    const result = await apiJson<BulkUpsertResponse>("/inventory/", {
      method: "POST",
      body: JSON.stringify({
        registros: stock.map((r) => ({
          clasificador: r.clasificador,
          stock_actual: Number(r.stockActual),
          stock_minimo: stockMinimoByCategoria[r.clasificador] ?? 0,
        })),
      }),
    });
    stockActualizado = result.rows_upserted;
    erroresVentas = [...erroresVentas, ...result.errors.map((e) => e.reason)];
  }

  return { ventasGuardadas, stockActualizado, erroresVentas };
}

export async function uploadSalesFile(file: File): Promise<BulkUpsertResponse> {
  const body = new FormData();
  body.append("file", file);
  return apiJson<BulkUpsertResponse>("/sales-history/upload", { method: "POST", body });
}

export async function uploadStockFile(file: File): Promise<BulkUpsertResponse> {
  const body = new FormData();
  body.append("file", file);
  return apiJson<BulkUpsertResponse>("/inventory/upload", { method: "POST", body });
}

async function downloadTemplate(path: string, fallbackName: string): Promise<void> {
  const { blob, filename } = await apiBlob(path);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename ?? fallbackName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function downloadSalesTemplate(): Promise<void> {
  await downloadTemplate("/sales-history/template", "plantilla_ventas.csv");
}

export async function downloadStockTemplate(): Promise<void> {
  await downloadTemplate("/inventory/upload/template", "plantilla_stock.csv");
}
