// Helpers de formato de fecha compartidos por todas las secciones del dashboard.

import type { PredictionHorizonte } from "@/lib/types";

const HORIZONTE_LABELS: Record<PredictionHorizonte, string> = {
  day: "Día",
  day_x: "Día X",
  week: "Semana",
  range: "Rango",
};

export function formatHorizonte(horizonte: PredictionHorizonte): string {
  return HORIZONTE_LABELS[horizonte] ?? horizonte;
}

export function formatFecha(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("es", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function formatDiaSemana(iso: string): string {
  const label = new Date(`${iso}T00:00:00`).toLocaleDateString("es", { weekday: "short" });
  return label.charAt(0).toUpperCase() + label.slice(1);
}

export function formatFechaHora(iso: string): string {
  return new Date(iso).toLocaleString("es", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
