// Descarga real de reportes PDF: GET /reports/weekly o /reports/monthly
// (solo admin). El backend siempre incluye todas las secciones del reporte
// hoy; las casillas de "datos a incluir" en la UI quedan listas para cuando
// el backend soporte reportes parciales. `clasificadores` si filtra: se
// manda como parametro repetido, igual que espera FastAPI para list[str].

import { apiBlob } from "./api";
import type { ReportOptions } from "./types";

export async function downloadReport(options: ReportOptions): Promise<{ filename: string }> {
  const path = options.horizonte === "week" ? "/reports/weekly" : "/reports/monthly";
  const params = new URLSearchParams({ fecha_inicio: options.fechaInicio });
  for (const clasificador of options.clasificadores ?? []) {
    params.append("clasificadores", clasificador);
  }
  const { blob, filename } = await apiBlob(`${path}?${params.toString()}`);

  const finalName = filename ?? `reporte_${options.horizonte}_${options.fechaInicio}.pdf`;
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = finalName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);

  return { filename: finalName };
}
