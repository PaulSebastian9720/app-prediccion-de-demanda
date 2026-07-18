"use client";

import { useState, type ComponentType } from "react";
import { Calendar, CalendarClock, CalendarRange, Info, Loader2, Search } from "lucide-react";
import { toast } from "sonner";
import { ExplanationCard } from "@/components/ExplanationCard";
import { ModelVersionSelector } from "@/components/ModelVersionSelector";
import { SectionHeader } from "@/components/SectionHeader";
import { fetchPredictionDayX, fetchPredictionRange } from "@/lib/api-predictions";
import { formatFecha } from "@/lib/format";
import {
  CLASIFICADORES,
  type PredictionDayXResult,
  type PredictionRangeResult,
} from "@/lib/types";
import { btnPrimary, cardClass, describeError, inputClass } from "@/lib/ui";

type PredMode = "dayx" | "week" | "month";

export function PrediccionesSection() {
  const [mode, setMode] = useState<PredMode>("dayx");
  const [clasificador, setClasificador] = useState(CLASIFICADORES[0].code);
  const [fechaObjetivo, setFechaObjetivo] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 14);
    return d.toISOString().slice(0, 10);
  });
  const [loading, setLoading] = useState(false);
  const [dayXResult, setDayXResult] = useState<PredictionDayXResult | null>(null);
  const [rangeResult, setRangeResult] = useState<PredictionRangeResult | null>(null);

  const todayIso = new Date().toISOString().slice(0, 10);

  async function handleConsult() {
    setLoading(true);
    try {
      if (mode === "dayx") {
        const result = await fetchPredictionDayX(clasificador, fechaObjetivo);
        setDayXResult(result);
        setRangeResult(null);
      } else {
        const dias = mode === "week" ? 7 : 30;
        const result = await fetchPredictionRange(clasificador, dias);
        setRangeResult(result);
        setDayXResult(null);
      }
    } catch (err) {
      toast.error(describeError(err, "No se pudo obtener la predicción."));
    } finally {
      setLoading(false);
    }
  }

  const predicciones = dayXResult?.predicciones_diarias ?? rangeResult?.predicciones_diarias ?? null;

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <SectionHeader
          title="Predicciones de demanda dia/semana/mes"
          description=""
        />
        <ModelVersionSelector />
      </div>

      <div className={`${cardClass} flex flex-wrap items-end gap-4 p-4 sm:p-5`}>
        <div>
          <span className="mb-1.5 block text-xs font-medium text-slate-500">
            Tipo de predicción
          </span>
          <div className="flex gap-1 rounded-lg bg-slate-100 p-1">
            <ModeButton
              icon={CalendarClock}
              label="Día X"
              active={mode === "dayx"}
              onClick={() => setMode("dayx")}
            />
            <ModeButton
              icon={CalendarRange}
              label="Semana"
              active={mode === "week"}
              onClick={() => setMode("week")}
            />
            <ModeButton
              icon={Calendar}
              label="Mes"
              active={mode === "month"}
              onClick={() => setMode("month")}
            />
          </div>
        </div>

        <div>
          <label htmlFor="clasificador" className="mb-1.5 block text-xs font-medium text-slate-500">
            Categoría
          </label>
          <select
            id="clasificador"
            value={clasificador}
            onChange={(e) => setClasificador(e.target.value)}
            className={inputClass}
          >
            {CLASIFICADORES.map((c) => (
              <option key={c.code} value={c.code}>
                {c.label}
              </option>
            ))}
          </select>
        </div>

        {mode === "dayx" && (
          <div>
            <label
              htmlFor="fechaObjetivo"
              className="mb-1.5 block text-xs font-medium text-slate-500"
            >
              Fecha objetivo
            </label>
            <input
              id="fechaObjetivo"
              type="date"
              min={todayIso}
              value={fechaObjetivo}
              onChange={(e) => setFechaObjetivo(e.target.value)}
              className={inputClass}
            />
          </div>
        )}

        <button onClick={handleConsult} disabled={loading} className={btnPrimary}>
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
          Consultar
        </button>
      </div>

      {mode === "dayx" && dayXResult && (
        <div className="space-y-4">
          {dayXResult.fecha_inicio !== dayXResult.fecha_objetivo && (
            <div className="flex items-start gap-2.5 rounded-lg border border-amber-200/80 bg-amber-50 px-3.5 py-3 text-sm text-amber-800">
              <Info className="mt-0.5 h-4 w-4 shrink-0" />
              <p>
                No hay historial contiguo hasta el {formatFecha(dayXResult.fecha_objetivo)}: el
                modelo encadenó {dayXResult.dias_proyectados} predicciones diarias desde el{" "}
                {formatFecha(dayXResult.fecha_inicio)} para llegar a la fecha pedida.
              </p>
            </div>
          )}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Stat
              label={`Predicción individual · ${formatFecha(dayXResult.fecha_objetivo)}`}
              value={dayXResult.prediccion_individual}
              suffix="u."
              highlight
            />
            <Stat
              label="Acumulado del periodo"
              value={dayXResult.prediccion_acumulada}
              suffix="u."
            />
            <Stat label="Días proyectados" value={dayXResult.dias_proyectados} />
          </div>
          {dayXResult.explicacion && (
            <ExplanationCard
              explicacion={dayXResult.explicacion}
              prediccion={dayXResult.prediccion_individual}
              defaultOpen
            />
          )}
        </div>
      )}

      {mode !== "dayx" && rangeResult && (
        <div className="space-y-4">
          <p className="text-sm text-slate-500">
            Del {formatFecha(rangeResult.fecha_inicio)} al {formatFecha(rangeResult.fecha_fin)}.
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Stat
              label="Total del periodo"
              value={rangeResult.total_periodo}
              suffix="u."
              highlight
            />
            <Stat
              label="Promedio diario"
              value={Math.round(rangeResult.total_periodo / rangeResult.dias)}
              suffix="u."
            />
            <Stat label="Días proyectados" value={rangeResult.dias} />
          </div>
          {rangeResult.explicacion && (
            <ExplanationCard
              explicacion={rangeResult.explicacion}
              prediccion={rangeResult.total_periodo}
              defaultOpen
            />
          )}
        </div>
      )}

      {!predicciones && !loading && (
        <div className={`${cardClass} border-dashed px-6 py-12 text-center`}>
          <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-slate-100">
            <Search className="h-5 w-5 text-slate-400" />
          </span>
          <p className="mt-4 text-sm font-medium text-slate-700">Sin consultas todavía</p>
          <p className="mx-auto mt-1 max-w-sm text-sm text-slate-500">
            Elige una categoría y una temporalidad, después presiona «Consultar» para ver la
            proyección del modelo.
          </p>
        </div>
      )}
    </section>
  );
}

function ModeButton({
  icon: Icon,
  label,
  active,
  onClick,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500/40 ${
        active ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"
      }`}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
    </button>
  );
}

function Stat({
  label,
  value,
  suffix,
  highlight = false,
}: {
  label: string;
  value: number;
  suffix?: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={
        highlight ? "rounded-xl bg-accent-600 p-4 shadow-card sm:p-5" : `${cardClass} p-4 sm:p-5`
      }
    >
      <p className={`text-xs font-medium ${highlight ? "text-accent-100" : "text-slate-500"}`}>
        {label}
      </p>
      <p
        className={`mt-1.5 font-mono text-3xl font-semibold tracking-tight tabular-nums ${
          highlight ? "text-white" : "text-slate-900"
        }`}
      >
        {value.toLocaleString("es")}
        {suffix && (
          <span
            className={`ml-1.5 text-sm font-normal ${
              highlight ? "text-accent-200" : "text-slate-400"
            }`}
          >
            {suffix}
          </span>
        )}
      </p>
    </div>
  );
}
