"use client";

// Lista paginada de predicciones pasadas de cualquier horizonte (/day,
// /day-x por dia; /week y /range en conjunto), con acceso al detalle +
// explicacion guardada de cada una.

import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Eye, Loader2, Search } from "lucide-react";
import { toast } from "sonner";
import { PredictionHistoryDetailModal } from "@/components/PredictionHistoryDetailModal";
import { ApiError } from "@/lib/api";
import { fetchPredictionHistory } from "@/lib/api-predictions";
import { formatFecha, formatHorizonte } from "@/lib/format";
import { CLASIFICADORES, type PredictionHistoryItem } from "@/lib/types";
import { btnSecondary, cardClass, inputClass } from "@/lib/ui";

const PAGE_SIZE = 10;

export function PredictionHistoryTable() {
  const [clasificador, setClasificador] = useState<string>("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<PredictionHistoryItem[]>([]);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    // Necesario en cada re-fetch (cambio de pagina/filtro), no solo al montar:
    // sin esto, la tabla anterior queda visible mientras carga la siguiente.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    fetchPredictionHistory({
      clasificador: clasificador || undefined,
      page,
      pageSize: PAGE_SIZE,
    })
      .then((data) => {
        if (!active) return;
        setItems(data.items);
        setTotalPages(data.meta.total_pages);
      })
      .catch((err) => {
        const message =
          err instanceof ApiError ? err.message : "No se pudo cargar el historial de predicciones.";
        toast.error(message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [clasificador, page]);

  return (
    <div className="space-y-4">
      <div className={`${cardClass} flex flex-wrap items-end gap-4 p-4 sm:p-5`}>
        <div>
          <label htmlFor="filtroClasificador" className="mb-1.5 block text-xs font-medium text-slate-500">
            Categoría
          </label>
          <select
            id="filtroClasificador"
            value={clasificador}
            onChange={(e) => {
              setClasificador(e.target.value);
              setPage(1);
            }}
            className={inputClass}
          >
            <option value="">Todas las categorías</option>
            {CLASIFICADORES.map((c) => (
              <option key={c.code} value={c.code}>
                {c.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
        </div>
      )}

      {!loading && items.length === 0 && (
        <div className={`${cardClass} border-dashed px-6 py-12 text-center`}>
          <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-slate-100">
            <Search className="h-5 w-5 text-slate-400" />
          </span>
          <p className="mt-4 text-sm font-medium text-slate-700">Sin predicciones registradas</p>
          <p className="mx-auto mt-1 max-w-sm text-sm text-slate-500">
            Cuando consultes la predicción de un día específico, aparecerá aquí junto con su
            explicación.
          </p>
        </div>
      )}

      {!loading && items.length > 0 && (
        <>
          <div className={`${cardClass} overflow-hidden`}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/80 text-left text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
                    <th className="px-4 py-2.5 font-semibold">Fecha</th>
                    <th className="px-4 py-2.5 font-semibold">Horizonte</th>
                    <th className="px-4 py-2.5 font-semibold">Categoría</th>
                    <th className="px-4 py-2.5 text-right font-semibold">Unidades</th>
                    <th className="px-4 py-2.5 font-semibold">Resumen</th>
                    <th className="px-4 py-2.5 font-semibold" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {items.map((item) => {
                    const label =
                      CLASIFICADORES.find((c) => c.code === item.clasificador)?.label ??
                      item.clasificador;
                    return (
                      <tr key={item.inference_log_id} className="transition-colors hover:bg-accent-50/40">
                        <td className="px-4 py-2.5 whitespace-nowrap text-slate-700">
                          {formatFecha(item.fecha)}
                        </td>
                        <td className="px-4 py-2.5 whitespace-nowrap">
                          <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                            {formatHorizonte(item.horizonte)}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-slate-700">{label}</td>
                        <td className="px-4 py-2.5 text-right font-mono font-medium tabular-nums text-slate-900">
                          {item.cantidad_predicha}
                        </td>
                        <td className="max-w-xs truncate px-4 py-2.5 text-slate-500">
                          {item.resumen ?? "—"}
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          <button
                            onClick={() => setSelectedId(item.inference_log_id)}
                            className={btnSecondary}
                          >
                            <Eye className="h-3.5 w-3.5" />
                            Ver
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className={btnSecondary}
              >
                <ChevronLeft className="h-3.5 w-3.5" />
                Anterior
              </button>
              <span className="text-xs text-slate-500">
                Página {page} de {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className={btnSecondary}
              >
                Siguiente
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </>
      )}

      {selectedId && (
        <PredictionHistoryDetailModal
          inferenceLogId={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  );
}
