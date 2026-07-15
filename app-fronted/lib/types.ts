// Tipos compartidos por las paginas del dashboard. Los nombres de campos
// coinciden a proposito con los schemas Pydantic del backend
// (app-backend/src/app/schemas/prediction.py y sales_history.py) para que
// cambiar de las funciones mock (lib/mock-api.ts) a fetch() real sea directo.

export interface Clasificador {
  code: string;
  label: string;
}

export const CLASIFICADORES: Clasificador[] = [
  { code: "ALIMENTACION_HIDRATACION", label: "Alimentación e Hidratación" },
  { code: "DESCANSO", label: "Descanso" },
  { code: "HIGIENE_ASEO", label: "Higiene y Aseo" },
  { code: "IDENTIFICACION_LOCALIZACION", label: "Identificación y Localización" },
  { code: "JUGUETES", label: "Juguetes" },
  { code: "OTROS_ACCESORIOS", label: "Otros Accesorios" },
  { code: "PASEO_SUJECION", label: "Paseo y Sujeción" },
  { code: "TRANSPORTE_VIAJE", label: "Transporte y Viaje" },
  { code: "VESTIMENTA", label: "Vestimenta" },
];

export interface DailyPrediction {
  fecha: string; // YYYY-MM-DD
  cantidad: number;
}

// Explicacion XAI de una prediccion de un dia especifico (/predictions/day y
// /predictions/day-x). Los `factores` ya vienen calculados y ordenados por el
// backend (perturbacion real del modelo, no una aproximacion) -- el frontend
// solo los renderiza, no los reinterpreta.
export interface ExplanationFactor {
  factor: string;
  impacto_unidades: number;
  direccion: "sube" | "baja";
  descripcion: string;
}

export interface DiaSimilar {
  fecha: string;
  cantidad: number;
}

export interface PredictionExplanation {
  resumen: string;
  factores: ExplanationFactor[];
  dia_similar: DiaSimilar | null;
  margen_error_habitual: number | null;
  // Promedio historico de ventas en ESE mismo dia de la semana. Solo
  // /day y /day-x; null en explicaciones de periodo (/week, /range).
  promedio_dia_semana: number | null;
  // Stock fisico actual de la categoria al generar la explicacion, para
  // comparar contra la demanda predicha. Null si no hay stock cargado.
  stock_actual: number | null;
  recomendacion: string | null;
  generado_por: "llm" | "fallback";
  // Ultimos ~14 dias de historial real antes de la fecha explicada, para
  // dibujar una tendencia simple junto al texto. En /day y /day-x son dias
  // individuales; en /week y /range (explicacion de periodo, `factores`
  // vacio) es el historial antes del periodo completo.
  historial_reciente: DailyPrediction[];
}

export interface PredictionDayXResult {
  clasificador: string;
  fecha_inicio: string;
  fecha_objetivo: string;
  dias_proyectados: number;
  prediccion_individual: number;
  prediccion_acumulada: number;
  predicciones_diarias: DailyPrediction[];
  model_version: string;
  inference_log_id: string;
  explicacion: PredictionExplanation | null;
}

export type PredictionHorizonte = "day" | "day_x" | "week" | "range";

export interface PredictionHistoryItem {
  inference_log_id: string;
  clasificador: string;
  horizonte: PredictionHorizonte;
  fecha: string;
  cantidad_predicha: number;
  resumen: string | null;
  created_at: string;
}

export interface PredictionHistoryDetail {
  inference_log_id: string;
  clasificador: string;
  horizonte: PredictionHorizonte;
  fecha: string;
  cantidad_predicha: number;
  model_version: string;
  created_at: string;
  explicacion: PredictionExplanation | null;
}

export interface PaginationMeta {
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  meta: PaginationMeta;
}

export interface PredictionRangeResult {
  clasificador: string;
  fecha_inicio: string;
  fecha_fin: string;
  dias: number;
  predicciones_diarias: DailyPrediction[];
  total_periodo: number;
  model_version: string;
  inference_log_id: string;
  // Explicacion EN CONJUNTO del periodo completo (una sola llamada al LLM,
  // no una por dia): `factores` viene vacio y `dia_similar` es null.
  explicacion: PredictionExplanation | null;
}

export type ReportHorizonte = "week" | "month";

export interface ReportOptions {
  horizonte: ReportHorizonte;
  fechaInicio: string;
  incluirStockCritico: boolean;
  incluirSugerenciasLlm: boolean;
  incluirGraficas: boolean;
  incluirCostos: boolean;
  // Subconjunto de categorias a incluir; vacio/undefined = todas.
  clasificadores?: string[];
}

export interface IngestRow {
  clasificador: string;
  cantidadVendida: string;
  precioMedio: string;
  stockActual: string;
}

export function createEmptyIngestRows(): IngestRow[] {
  return CLASIFICADORES.map((c) => ({
    clasificador: c.code,
    cantidadVendida: "",
    precioMedio: "",
    stockActual: "",
  }));
}
