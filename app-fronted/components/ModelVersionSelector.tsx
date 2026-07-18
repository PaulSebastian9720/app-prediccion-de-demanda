"use client";

// Selector compacto del modelo ACTIVO (global, mismo backend que el panel de
// "Datos y Modelo"): a mano en Predicciones/Reportes para no tener que ir a
// otra pagina solo para cambiar que version de modelo esta sirviendo. Elegir
// una version distinta la activa para TODOS (no es una preview local).

import { useEffect, useState } from "react";
import { BrainCircuit, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { activateModelVersion, listModelVersions, type ModelVersion } from "@/lib/api-retraining";
import { getStoredAuth, isAdmin } from "@/lib/auth";
import { describeError } from "@/lib/ui";

export function ModelVersionSelector() {
  const admin = isAdmin(getStoredAuth()?.user);
  const [versions, setVersions] = useState<ModelVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [switching, setSwitching] = useState(false);

  async function cargar() {
    try {
      setVersions(await listModelVersions());
    } catch {
      // Silencioso: no bloquear la pagina de predicciones/reportes por esto.
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- carga inicial desde el backend, no hay otra forma de poblar el estado.
    cargar();
  }, []);

  const activa = versions.find((v) => v.is_active);

  async function handleChange(versionId: string) {
    if (!versionId || versionId === activa?.id) return;
    setSwitching(true);
    try {
      await activateModelVersion(versionId);
      toast.success("Modelo activo actualizado.");
      await cargar();
    } catch (err) {
      toast.error(describeError(err, "No se pudo cambiar el modelo activo."));
    } finally {
      setSwitching(false);
    }
  }

  if (loading || versions.length === 0) return null;

  if (!admin) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
        <BrainCircuit className="h-3.5 w-3.5 text-slate-400" />
        Modelo v{activa?.version_number.toString().padStart(3, "0")}
      </span>
    );
  }

  return (
    <label className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white py-1 pr-2.5 pl-2.5 text-xs font-medium text-slate-600 shadow-xs">
      {switching ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400" />
      ) : (
        <BrainCircuit className="h-3.5 w-3.5 text-slate-400" />
      )}
      <span className="text-slate-400">Modelo</span>
      <select
        value={activa?.id ?? ""}
        onChange={(e) => handleChange(e.target.value)}
        disabled={switching}
        className="cursor-pointer bg-transparent font-mono text-xs font-semibold text-slate-700 outline-none disabled:cursor-not-allowed"
      >
        {versions.map((v) => (
          <option key={v.id} value={v.id}>
            v{v.version_number.toString().padStart(3, "0")} · MAE {v.metrics.prueba.MAE.toFixed(2)}
            {v.is_active ? " (activo)" : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
