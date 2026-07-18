"use client";

// Explicacion XAI de una prediccion de un dia especifico (/predictions/day y
// /predictions/day-x). Los datos ya vienen calculados y verificados por el
// backend (perturbacion real del modelo, no una aproximacion de SHAP): este
// componente solo los presenta, no reinterpreta ni recalcula nada.

import { useState } from "react";
import {
  AlertTriangle,
  Calendar,
  ChevronDown,
  ChevronUp,
  PackageCheck,
  Sparkles,
  Target,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { formatFecha } from "@/lib/format";
import type { DailyPrediction, PredictionExplanation } from "@/lib/types";
import { cardClass } from "@/lib/ui";

export function ExplanationCard({
  explicacion,
  prediccion,
  defaultOpen = false,
}: {
  explicacion: PredictionExplanation;
  prediccion: number;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  // Los `factores` traen `impacto_unidades` con signo (positivo si "sube",
  // negativo si "baja") -- sumarlos hacia atras reconstruye el punto de
  // referencia del que partio el modelo antes de aplicar cada factor.
  const ancla = prediccion - explicacion.factores.reduce((acc, f) => acc + f.impacto_unidades, 0);
  const maxImpacto = Math.max(1, ...explicacion.factores.map((f) => Math.abs(f.impacto_unidades)));

  return (
    <div className={`${cardClass} overflow-hidden`}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition hover:bg-slate-50/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500/40 sm:px-5"
      >
        <span className="flex items-center gap-2 text-sm font-medium text-slate-700">
          <Sparkles className="h-4 w-4 text-accent-600" />
          ¿Por qué esta predicción?
        </span>
        {open ? (
          <ChevronUp className="h-4 w-4 shrink-0 text-slate-400" />
        ) : (
          <ChevronDown className="h-4 w-4 shrink-0 text-slate-400" />
        )}
      </button>

      {open && (
        <div className="space-y-4 border-t border-slate-200/80 px-4 py-4 sm:px-5">
          {explicacion.historial_reciente.length > 0 && (
            <TendenciaChart historial={explicacion.historial_reciente} prediccion={prediccion} />
          )}

          {explicacion.factores.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span>Punto de referencia habitual</span>
                <span className="font-mono font-medium tabular-nums text-slate-700">{ancla} u.</span>
              </div>
              {explicacion.factores.map((factor, i) => (
                <div key={i} className="flex items-center gap-2.5">
                  {factor.direccion === "sube" ? (
                    <TrendingUp className="h-3.5 w-3.5 shrink-0 text-emerald-600" />
                  ) : (
                    <TrendingDown className="h-3.5 w-3.5 shrink-0 text-amber-600" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-slate-700">{factor.factor}</p>
                    <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                      <div
                        className={`h-full rounded-full ${
                          factor.direccion === "sube" ? "bg-emerald-500" : "bg-amber-500"
                        }`}
                        style={{
                          width: `${(Math.abs(factor.impacto_unidades) / maxImpacto) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                  <span
                    className={`shrink-0 font-mono text-xs font-semibold tabular-nums ${
                      factor.direccion === "sube" ? "text-emerald-700" : "text-amber-700"
                    }`}
                  >
                    {factor.impacto_unidades >= 0 ? "+" : ""}
                    {factor.impacto_unidades} u.
                  </span>
                </div>
              ))}
              <div className="flex items-center justify-between border-t border-dashed border-slate-200 pt-2 text-xs">
                <span className="font-medium text-slate-700">Predicción final</span>
                <span className="font-mono font-semibold tabular-nums text-accent-700">
                  {prediccion} u.
                </span>
              </div>
            </div>
          )}

          {explicacion.margen_error_habitual !== null && (
            <RangoConfianza prediccion={prediccion} margenError={explicacion.margen_error_habitual} />
          )}

          {explicacion.promedio_dia_semana !== null && (
            <ComparacionDiaSemana prediccion={prediccion} promedio={explicacion.promedio_dia_semana} />
          )}

          {explicacion.stock_actual !== null && (
            <ComparacionStock prediccion={prediccion} stockActual={explicacion.stock_actual} />
          )}

          {explicacion.dia_similar && (
            <div className="flex items-start gap-2 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
              <Calendar className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
              <p>
                Se parece a lo ocurrido el <strong>{formatFecha(explicacion.dia_similar.fecha)}</strong>,
                cuando se vendieron <strong>{explicacion.dia_similar.cantidad} unidades</strong>.
              </p>
            </div>
          )}

          <p className="text-sm leading-relaxed text-slate-700">{explicacion.resumen}</p>

          {explicacion.recomendacion && (
            <p className="text-sm leading-relaxed text-slate-600 italic">
              💡 {explicacion.recomendacion}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/** Banda de rango probable alrededor de la predicción, calculada con el
 * margen de error (MAE) real ya medido contra ventas pasadas -- en vez de
 * solo un texto "±X u.", muestra visualmente entre qué dos números es
 * probable que caiga la demanda real. */
function RangoConfianza({ prediccion, margenError }: { prediccion: number; margenError: number }) {
  const bajo = Math.max(0, Math.round(prediccion - margenError));
  const alto = Math.round(prediccion + margenError);
  const maxEscala = Math.max(alto, 1);
  const pctBajo = (bajo / maxEscala) * 100;
  const pctAlto = (alto / maxEscala) * 100;
  const pctPred = (prediccion / maxEscala) * 100;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
        <Target className="h-3.5 w-3.5" />
        Rango probable de la demanda real
      </div>
      <div className="relative h-2 w-full rounded-full bg-slate-100">
        <div
          className="absolute h-full rounded-full bg-accent-200"
          style={{ left: `${pctBajo}%`, width: `${Math.max(2, pctAlto - pctBajo)}%` }}
        />
        <div
          className="absolute top-1/2 h-3 w-3 -translate-y-1/2 rounded-full border-2 border-white bg-accent-600 shadow"
          style={{ left: `calc(${pctPred}% - 6px)` }}
        />
      </div>
      <p className="text-xs text-slate-500">
        Es probable que esté entre <strong className="text-slate-700">{bajo}</strong> y{" "}
        <strong className="text-slate-700">{alto}</strong> unidades (margen de error habitual del
        sistema: ±{margenError} u.).
      </p>
    </div>
  );
}

/** Compara la predicción con el promedio histórico de ESE mismo día de la
 * semana (ej. el promedio de todos los miércoles anteriores) -- ayuda a
 * explicar parte del "por qué" sin mencionar nada técnico. */
function ComparacionDiaSemana({ prediccion, promedio }: { prediccion: number; promedio: number }) {
  const max = Math.max(prediccion, promedio, 1);
  const diff = prediccion - promedio;
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium text-slate-500">Comparado con este mismo día, otras veces</p>
      <MiniBarRow label="Hoy (predicho)" valor={prediccion} max={max} color="bg-accent-600" />
      <MiniBarRow label="Promedio de este día" valor={promedio} max={max} color="bg-slate-300" />
      {Math.abs(diff) >= 1 && (
        <p className="text-xs text-slate-500">
          {diff > 0 ? "+" : ""}
          {Math.round(diff)} u. {diff > 0 ? "por encima" : "por debajo"} de lo habitual para este
          día de la semana.
        </p>
      )}
    </div>
  );
}

/** Compara la demanda predicha contra el stock físico actual de la
 * categoría (dato de inventario, independiente del modelo) -- el punto más
 * accionable: ¿alcanza lo que hay en bodega? */
function ComparacionStock({ prediccion, stockActual }: { prediccion: number; stockActual: number }) {
  const alcanza = stockActual >= prediccion;
  const max = Math.max(prediccion, stockActual, 1);
  return (
    <div className="space-y-1.5">
      <div
        className={`flex items-center gap-1.5 text-xs font-medium ${
          alcanza ? "text-emerald-700" : "text-amber-700"
        }`}
      >
        {alcanza ? (
          <PackageCheck className="h-3.5 w-3.5" />
        ) : (
          <AlertTriangle className="h-3.5 w-3.5" />
        )}
        Stock actual vs. demanda esperada
      </div>
      <MiniBarRow label="Demanda esperada" valor={prediccion} max={max} color="bg-accent-600" />
      <MiniBarRow
        label="Stock actual"
        valor={stockActual}
        max={max}
        color={alcanza ? "bg-emerald-500" : "bg-amber-500"}
      />
      <p className="text-xs text-slate-500">
        {alcanza
          ? "El stock actual cubre la demanda esperada."
          : `Podrías quedarte corto por ~${Math.round(prediccion - stockActual)} u.`}
      </p>
    </div>
  );
}

function MiniBarRow({
  label,
  valor,
  max,
  color,
}: {
  label: string;
  valor: number;
  max: number;
  color: string;
}) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-32 shrink-0 truncate text-slate-500">{label}</span>
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${Math.max(2, (valor / max) * 100)}%` }}
        />
      </div>
      <span className="w-14 shrink-0 text-right font-mono tabular-nums text-slate-700">
        {Math.round(valor)} u.
      </span>
    </div>
  );
}

/** Grafico de barras simple: los ultimos ~14 dias de historial real, con la
 * predicción resaltada en un color distinto al final -- la manera "no
 * técnica" de ver la tendencia que llevó a este número, sin ejes ni
 * leyendas complejas. */
function TendenciaChart({
  historial,
  prediccion,
}: {
  historial: DailyPrediction[];
  prediccion: number;
}) {
  const maxValor = Math.max(...historial.map((d) => d.cantidad), prediccion, 1);

  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium text-slate-500">Tendencia reciente</p>
      <div className="flex h-20 items-end gap-1">
        {historial.map((dia) => (
          <div key={dia.fecha} className="group relative h-full flex-1">
            <div
              className="absolute right-0 bottom-0 left-0 rounded-t-sm bg-slate-300 transition-colors group-hover:bg-slate-400"
              style={{ height: `${Math.max(4, (dia.cantidad / maxValor) * 100)}%` }}
            />
            <span className="pointer-events-none absolute -top-6 left-1/2 -translate-x-1/2 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] whitespace-nowrap text-white opacity-0 transition-opacity group-hover:opacity-100">
              {formatFecha(dia.fecha)}: {dia.cantidad} u.
            </span>
          </div>
        ))}
        <div className="group relative h-full flex-1">
          <div
            className="absolute right-0 bottom-0 left-0 rounded-t-sm bg-accent-600"
            style={{ height: `${Math.max(4, (prediccion / maxValor) * 100)}%` }}
          />
          <span className="pointer-events-none absolute -top-6 left-1/2 -translate-x-1/2 rounded bg-accent-700 px-1.5 py-0.5 text-[10px] whitespace-nowrap text-white opacity-0 transition-opacity group-hover:opacity-100">
            Predicción: {prediccion} u.
          </span>
        </div>
      </div>
      <div className="flex items-center gap-1.5 text-[10px] text-slate-400">
        <span className="inline-block h-2 w-2 rounded-sm bg-slate-300" /> Historial real
        <span className="ml-2 inline-block h-2 w-2 rounded-sm bg-accent-600" /> Predicción
      </div>
    </div>
  );
}
