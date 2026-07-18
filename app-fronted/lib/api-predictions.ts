// Predicciones reales contra POST /predictions/day-x, /week y /range, y el
// historial de predicciones de un dia especifico (GET /predictions/history*).

import { apiJson } from "./api";
import type {
  PaginatedResponse,
  PredictionDayXResult,
  PredictionHistoryDetail,
  PredictionHistoryItem,
  PredictionRangeResult,
} from "./types";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export async function fetchPredictionDayX(
  clasificador: string,
  fechaObjetivo: string,
): Promise<PredictionDayXResult> {
  return apiJson<PredictionDayXResult>("/predictions/day-x", {
    method: "POST",
    body: JSON.stringify({ clasificador, fecha_objetivo: fechaObjetivo }),
  });
}

export async function fetchPredictionRange(
  clasificador: string,
  dias: 7 | 30,
): Promise<PredictionRangeResult> {
  if (dias === 7) {
    return apiJson<PredictionRangeResult>("/predictions/week", {
      method: "POST",
      body: JSON.stringify({ clasificador, fecha_inicio: todayIso() }),
    });
  }
  return apiJson<PredictionRangeResult>("/predictions/range", {
    method: "POST",
    body: JSON.stringify({ clasificador, fecha_inicio: todayIso(), dias }),
  });
}

export interface PredictionHistoryFilters {
  clasificador?: string;
  fromDate?: string;
  toDate?: string;
  page?: number;
  pageSize?: number;
}

export async function fetchPredictionHistory(
  filters: PredictionHistoryFilters = {},
): Promise<PaginatedResponse<PredictionHistoryItem>> {
  const params = new URLSearchParams();
  if (filters.clasificador) params.set("clasificador", filters.clasificador);
  if (filters.fromDate) params.set("from_date", filters.fromDate);
  if (filters.toDate) params.set("to_date", filters.toDate);
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? 20));

  return apiJson<PaginatedResponse<PredictionHistoryItem>>(
    `/predictions/history?${params.toString()}`,
  );
}

export async function fetchPredictionHistoryDetail(
  inferenceLogId: string,
): Promise<PredictionHistoryDetail> {
  return apiJson<PredictionHistoryDetail>(`/predictions/history/${inferenceLogId}`);
}
