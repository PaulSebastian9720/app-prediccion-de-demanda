"use client";

// Panel de reentrenamiento + versionado del modelo: dispara un reentrenamiento
// real (RandomizedSearchCV sobre TODO el historial ya ingerido, no un CSV
// fijo), lo sondea hasta que termina, y muestra el historial de versiones con
// sus metricas -- la version con mejor MAE de prueba se activa sola; el resto
// queda disponible para activar a mano.

import { useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2, Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import {
  activateModelVersion,
  getRetrainingJob,
  listModelVersions,
  listRetrainingJobs,
  triggerRetraining,
  type ModelVersion,
  type RetrainingJob,
} from "@/lib/api-retraining";
import { ApiError } from "@/lib/api";
import { getStoredAuth, isAdmin } from "@/lib/auth";
import { formatFechaHora } from "@/lib/format";
import { btnPrimary, btnSecondary, cardClass, describeError } from "@/lib/ui";

const POLL_INTERVAL_MS = 3000;

const ESTADO_LABEL: Record<RetrainingJob["status"], string> = {
  pending: "Pendiente",
  running: "Entrenando…",
  success: "Completado",
  failed: "Falló",
};

export function RetrainingPanel() {
  const admin = isAdmin(getStoredAuth()?.user);
  const [versions, setVersions] = useState<ModelVersion[]>([]);
  const [activeJob, setActiveJob] = useState<RetrainingJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [activatingId, setActivatingId] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const cargarVersiones = useCallback(async () => {
    try {
      const data = await listModelVersions();
      setVersions(data);
    } catch (err) {
      toast.error(describeError(err, "No se pudo cargar el historial de versiones."));
    }
  }, []);

  const detenerPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const seguirJob = useCallback(
    (jobId: string) => {
      detenerPolling();
      pollRef.current = setInterval(async () => {
        try {
          const job = await getRetrainingJob(jobId);
          setActiveJob(job);
          if (job.status === "success" || job.status === "failed") {
            detenerPolling();
            setActiveJob(null);
            if (job.status === "success") {
              toast.success("Reentrenamiento completado.");
            } else {
              toast.error(job.error_message ?? "El reentrenamiento falló.");
            }
            await cargarVersiones();
          }
        } catch {
          detenerPolling();
        }
      }, POLL_INTERVAL_MS);
    },
    [cargarVersiones, detenerPolling],
  );

  useEffect(() => {
    (async () => {
      await cargarVersiones();
      try {
        const jobs = await listRetrainingJobs(1, 1);
        const ultimo = jobs.items[0];
        if (ultimo && (ultimo.status === "pending" || ultimo.status === "running")) {
          setActiveJob(ultimo);
          seguirJob(ultimo.id);
        }
      } finally {
        setLoading(false);
      }
    })();
    return () => detenerPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleTrigger() {
    try {
      const job = await triggerRetraining();
      setActiveJob(job);
      toast.info("Reentrenamiento en curso -- puede tardar unos minutos.");
      seguirJob(job.id);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        toast.warning("Ya hay un reentrenamiento en curso.");
      } else if (err instanceof ApiError && err.status === 403) {
        toast.error("Se requiere rol de administrador para reentrenar.");
      } else {
        toast.error(describeError(err, "No se pudo disparar el reentrenamiento."));
      }
    }
  }

  async function handleActivate(versionId: string) {
    setActivatingId(versionId);
    try {
      await activateModelVersion(versionId);
      toast.success("Versión activada.");
      await cargarVersiones();
    } catch (err) {
      toast.error(describeError(err, "No se pudo activar esa versión."));
    } finally {
      setActivatingId(null);
    }
  }

  const enProgreso = activeJob !== null;
  const activa = versions.find((v) => v.is_active);

  return (
    <div className={`${cardClass} space-y-4 p-4 sm:p-5`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-700">Reentrenamiento del modelo</h3>
          <p className="mt-1 text-xs text-slate-500">
            Reentrena desde cero con todo el historial ya cargado. La versión con mejor error de
            prueba (MAE) se activa sola; las demás quedan disponibles para activar a mano.
          </p>
        </div>
        {admin && (
          <button onClick={handleTrigger} disabled={enProgreso} className={btnPrimary}>
            {enProgreso ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {enProgreso ? (activeJob ? ESTADO_LABEL[activeJob.status] : "Entrenando…") : "Reentrenar modelo"}
          </button>
        )}
      </div>

      {activa && (
        <div className="flex items-center gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
          <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
          Versión activa: v{activa.version_number.toString().padStart(3, "0")} · MAE de prueba{" "}
          {activa.metrics.prueba.MAE.toFixed(2)} u.
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
        </div>
      ) : versions.length === 0 ? (
        <p className="py-4 text-center text-xs text-slate-400">
          Todavía no hay versiones entrenadas.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
                <th className="py-2 pr-3 font-semibold">Versión</th>
                <th className="py-2 pr-3 font-semibold">Entrenado el</th>
                <th className="py-2 pr-3 text-right font-semibold">MAE prueba</th>
                <th className="py-2 pr-3 text-right font-semibold">R² prueba</th>
                <th className="py-2 font-semibold" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {versions.map((v) => (
                <tr key={v.id} className="text-slate-700">
                  <td className="py-2 pr-3 font-mono">
                    v{v.version_number.toString().padStart(3, "0")}
                    {v.is_active && (
                      <span className="ml-1.5 rounded-full bg-accent-50 px-1.5 py-0.5 text-[10px] font-semibold text-accent-700 uppercase">
                        activa
                      </span>
                    )}
                  </td>
                  <td className="py-2 pr-3 text-slate-500">{formatFechaHora(v.fecha_entrenamiento)}</td>
                  <td className="py-2 pr-3 text-right font-mono tabular-nums">
                    {v.metrics.prueba.MAE.toFixed(2)}
                  </td>
                  <td className="py-2 pr-3 text-right font-mono tabular-nums">
                    {v.metrics.prueba.R2.toFixed(2)}
                  </td>
                  <td className="py-2 text-right">
                    {admin && !v.is_active && (
                      <button
                        onClick={() => handleActivate(v.id)}
                        disabled={activatingId === v.id}
                        className={btnSecondary}
                      >
                        {activatingId === v.id && <Loader2 className="h-3 w-3 animate-spin" />}
                        Activar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
