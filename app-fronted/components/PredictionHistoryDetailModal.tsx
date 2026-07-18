"use client";

// Modal de detalle de una prediccion pasada: lee la explicacion YA
// persistida via GET /predictions/history/{id} -- no vuelve a llamar al LLM
// ni recalcula nada, es una consulta directa a la base de datos.

import { useEffect, useState } from "react";
import { Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { ExplanationCard } from "@/components/ExplanationCard";
import { ApiError } from "@/lib/api";
import { fetchPredictionHistoryDetail } from "@/lib/api-predictions";
import { formatFecha, formatFechaHora, formatHorizonte } from "@/lib/format";
import { CLASIFICADORES, type PredictionHistoryDetail } from "@/lib/types";
import { btnSecondary, cardClass } from "@/lib/ui";

export function PredictionHistoryDetailModal({
  inferenceLogId,
  onClose,
}: {
  inferenceLogId: string;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<PredictionHistoryDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    // Necesario si `inferenceLogId` cambia con el modal ya montado: sin
    // esto, el detalle anterior queda visible mientras carga el siguiente.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    fetchPredictionHistoryDetail(inferenceLogId)
      .then((data) => {
        if (active) setDetail(data);
      })
      .catch((err) => {
        const message =
          err instanceof ApiError ? err.message : "No se pudo cargar el detalle de la predicción.";
        toast.error(message);
        onClose();
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [inferenceLogId, onClose]);

  const clasificadorLabel = detail
    ? (CLASIFICADORES.find((c) => c.code === detail.clasificador)?.label ?? detail.clasificador)
    : "";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4 py-8 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className={`${cardClass} max-h-full w-full max-w-lg overflow-y-auto`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-200/80 px-4 py-3 sm:px-5">
          <span className="text-sm font-semibold text-slate-900">Detalle de la predicción</span>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500/40"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
          </div>
        )}

        {!loading && detail && (
          <div className="space-y-4 p-4 sm:p-5">
            <div>
              <p className="flex items-center gap-2 text-xs font-medium text-slate-500">
                <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                  {formatHorizonte(detail.horizonte)}
                </span>
                {clasificadorLabel} · {formatFecha(detail.fecha)}
              </p>
              <p className="mt-1 font-mono text-3xl font-semibold tracking-tight tabular-nums text-slate-900">
                {detail.cantidad_predicha}
                <span className="ml-1.5 text-sm font-normal text-slate-400">unidades predichas</span>
              </p>
            </div>

            {detail.explicacion && (
              <ExplanationCard
                explicacion={detail.explicacion}
                prediccion={detail.cantidad_predicha}
                defaultOpen
              />
            )}

            <p className="text-xs text-slate-400">
              Modelo {detail.model_version} · consultado el {formatFechaHora(detail.created_at)}
            </p>

            <button onClick={onClose} className={`${btnSecondary} w-full`}>
              Cerrar
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
