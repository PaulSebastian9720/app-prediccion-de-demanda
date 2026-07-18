// Reentrenamiento real + versionado del modelo: POST /retraining/trigger,
// GET /retraining/jobs(/{id}), GET /retraining/versions,
// POST /retraining/versions/{id}/activate.

import { apiJson } from "./api";
import type { PaginatedResponse } from "./types";

export type RetrainingJobStatus = "pending" | "running" | "success" | "failed";

export interface RetrainingJob {
  id: string;
  status: RetrainingJobStatus;
  triggered_by_user_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  model_version_id: string | null;
  created_at: string;
}

export interface ModelMetrics {
  MAE: number;
  RMSE: number;
  R2: number;
}

export interface ModelVersion {
  id: string;
  version_number: number;
  fecha_entrenamiento: string;
  metrics: { validacion: ModelMetrics; prueba: ModelMetrics };
  is_active: boolean;
  created_at: string;
}

export async function triggerRetraining(): Promise<RetrainingJob> {
  return apiJson<RetrainingJob>("/retraining/trigger", { method: "POST" });
}

export async function listRetrainingJobs(
  page = 1,
  pageSize = 5,
): Promise<PaginatedResponse<RetrainingJob>> {
  return apiJson<PaginatedResponse<RetrainingJob>>(
    `/retraining/jobs?page=${page}&page_size=${pageSize}`,
  );
}

export async function getRetrainingJob(jobId: string): Promise<RetrainingJob> {
  return apiJson<RetrainingJob>(`/retraining/jobs/${jobId}`);
}

export async function listModelVersions(): Promise<ModelVersion[]> {
  return apiJson<ModelVersion[]>("/retraining/versions");
}

export async function activateModelVersion(versionId: string): Promise<ModelVersion> {
  return apiJson<ModelVersion>(`/retraining/versions/${versionId}/activate`, { method: "POST" });
}
