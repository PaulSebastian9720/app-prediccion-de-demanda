"use client";

import { useState, type ComponentType } from "react";
import { AlertTriangle, BarChart3, DollarSign, FileDown, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { ModelVersionSelector } from "@/components/ModelVersionSelector";
import { SectionHeader } from "@/components/SectionHeader";
import { ApiError } from "@/lib/api";
import { downloadReport } from "@/lib/api-reports";
import { CLASIFICADORES, type ReportHorizonte, type ReportOptions } from "@/lib/types";
import { btnPrimary, cardClass, describeError, inputClass } from "@/lib/ui";

export function ReportesSection() {
  const [horizonte, setHorizonte] = useState<ReportHorizonte>("week");
  const [fechaInicio, setFechaInicio] = useState(() => new Date().toISOString().slice(0, 10));
  const [incluirStockCritico, setIncluirStockCritico] = useState(true);
  const [incluirSugerenciasLlm, setIncluirSugerenciasLlm] = useState(true);
  const [incluirGraficas, setIncluirGraficas] = useState(true);
  const [incluirCostos, setIncluirCostos] = useState(true);
  const [categoriasSeleccionadas, setCategoriasSeleccionadas] = useState<string[]>(
    CLASIFICADORES.map((c) => c.code),
  );
  const [loading, setLoading] = useState(false);

  function toggleCategoria(code: string) {
    setCategoriasSeleccionadas((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
    );
  }

  async function handleDownload() {
    if (categoriasSeleccionadas.length === 0) {
      toast.error("Selecciona al menos una categoría para el reporte.");
      return;
    }
    setLoading(true);
    try {
      const todasSeleccionadas = categoriasSeleccionadas.length === CLASIFICADORES.length;
      const options: ReportOptions = {
        horizonte,
        fechaInicio,
        incluirStockCritico,
        incluirSugerenciasLlm,
        incluirGraficas,
        incluirCostos,
        clasificadores: todasSeleccionadas ? undefined : categoriasSeleccionadas,
      };
      const { filename } = await downloadReport(options);
      toast.success(`Reporte descargado: ${filename}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        toast.error("Se requiere rol de administrador para generar reportes.");
      } else {
        toast.error(describeError(err, "No se pudo generar el reporte."));
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <SectionHeader
          title="Descarga de reportes"
          description=""
        />
        <ModelVersionSelector />
      </div>

      <div className="space-y-4">
        <div className={`${cardClass} flex flex-wrap items-end gap-4 p-4 sm:p-5`}>
          <div>
            <span className="mb-1.5 block text-xs font-medium text-slate-500">
              Periodo del reporte
            </span>
            <div className="flex gap-1 rounded-lg bg-slate-100 p-1">
              <button
                onClick={() => setHorizonte("week")}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500/40 ${
                  horizonte === "week"
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                Semanal (7 días)
              </button>
              <button
                onClick={() => setHorizonte("month")}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500/40 ${
                  horizonte === "month"
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                Mensual (30 días)
              </button>
            </div>
          </div>

          <div>
            <label
              htmlFor="fechaInicioReporte"
              className="mb-1.5 block text-xs font-medium text-slate-500"
            >
              Fecha de inicio
            </label>
            <input
              id="fechaInicioReporte"
              type="date"
              value={fechaInicio}
              onChange={(e) => setFechaInicio(e.target.value)}
              className={inputClass}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className={`${cardClass} p-4 sm:p-5`}>
            <div className="mb-3 flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">
                Categorías a incluir ({categoriasSeleccionadas.length}/{CLASIFICADORES.length})
              </span>
              <button
                type="button"
                onClick={() =>
                  setCategoriasSeleccionadas(
                    categoriasSeleccionadas.length === CLASIFICADORES.length
                      ? []
                      : CLASIFICADORES.map((c) => c.code),
                  )
                }
                className="rounded text-xs font-medium text-accent-700 transition hover:text-accent-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500/40"
              >
                {categoriasSeleccionadas.length === CLASIFICADORES.length ? "Ninguna" : "Todas"}
              </button>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2">
              {CLASIFICADORES.map((categoria) => (
                <label
                  key={categoria.code}
                  className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm text-slate-700 transition-colors hover:bg-slate-50"
                >
                  <input
                    type="checkbox"
                    checked={categoriasSeleccionadas.includes(categoria.code)}
                    onChange={() => toggleCategoria(categoria.code)}
                    className="h-4 w-4 rounded-sm border-slate-300 accent-accent-600"
                  />
                  {categoria.label}
                </label>
              ))}
            </div>
          </div>

          <div className={`${cardClass} p-4 sm:p-5`}>
            <span className="mb-1.5 block text-xs font-medium text-slate-500">
              Datos a incluir
            </span>
            <div className="space-y-1">
              <CheckboxRow
                icon={AlertTriangle}
                label="Tabla de stock crítico"
                checked={incluirStockCritico}
                onChange={setIncluirStockCritico}
              />
              <CheckboxRow
                icon={Sparkles}
                label="Resumen y sugerencias del LLM"
                checked={incluirSugerenciasLlm}
                onChange={setIncluirSugerenciasLlm}
              />
              <CheckboxRow
                icon={BarChart3}
                label="Gráficas de tendencia"
                checked={incluirGraficas}
                onChange={setIncluirGraficas}
              />
              <CheckboxRow
                icon={DollarSign}
                label="Tabla de costos de reposición"
                checked={incluirCostos}
                onChange={setIncluirCostos}
              />
            </div>
          </div>
        </div>

        <button
          onClick={handleDownload}
          disabled={loading || categoriasSeleccionadas.length === 0}
          className={btnPrimary}
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileDown className="h-4 w-4" />}
          {loading ? "Generando PDF…" : "Descargar PDF"}
        </button>
      </div>
    </section>
  );
}

function CheckboxRow({
  icon: Icon,
  label,
  checked,
  onChange,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm text-slate-700 transition-colors hover:bg-slate-50">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded-sm border-slate-300 accent-accent-600"
      />
      <Icon className="h-4 w-4 text-slate-400" />
      {label}
    </label>
  );
}
