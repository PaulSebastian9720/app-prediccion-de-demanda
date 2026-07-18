"use client";

// Carga manual fila por fila (una por categoria) de ventas/precio/stock del
// dia. Valida en JS -- no solo con atributos HTML `min`/`step`, que un valor
// pegado o escrito rapido puede saltarse -- antes de dejar guardar: sin
// negativos en ningun campo, y sin decimales en stock (unidades enteras).

import { useEffect, useState } from "react";
import { Loader2, Save } from "lucide-react";
import { toast } from "sonner";
import { ApiError } from "@/lib/api";
import {
  fetchCurrentStock,
  saveIngestRows,
  type InventoryStockRow,
} from "@/lib/api-inventory";
import { formatFecha } from "@/lib/format";
import { CLASIFICADORES, createEmptyIngestRows, type IngestRow } from "@/lib/types";
import { btnPrimary, cardClass, describeError, inputClass } from "@/lib/ui";

type Campo = "cantidadVendida" | "precioMedio" | "stockActual";

function validarCampo(campo: Campo, valor: string): string | null {
  if (valor === "") return null;
  const num = Number(valor);
  if (Number.isNaN(num)) return "Debe ser un número.";
  if (num < 0) return "No se permiten números negativos.";
  if (campo === "stockActual" && !Number.isInteger(num)) {
    return "El stock debe ser un número entero (sin decimales).";
  }
  return null;
}

export function IngestaManualTable() {
  const [fecha, setFecha] = useState(() => new Date().toISOString().slice(0, 10));
  const [rows, setRows] = useState<IngestRow[]>(createEmptyIngestRows());
  const [stockActualByCategoria, setStockActualByCategoria] = useState<
    Record<string, InventoryStockRow>
  >({});
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchCurrentStock()
      .then((stock) => {
        const map: Record<string, InventoryStockRow> = {};
        for (const row of stock) map[row.clasificador] = row;
        setStockActualByCategoria(map);
        setRows((prev) =>
          prev.map((row) => ({
            ...row,
            stockActual: map[row.clasificador]
              ? String(map[row.clasificador].stock_actual)
              : row.stockActual,
          })),
        );
      })
      .catch((err) => toast.error(describeError(err, "No se pudo cargar el stock actual.")));
  }, []);

  function updateRow(index: number, field: Campo, value: string) {
    setRows((prev) => prev.map((row, i) => (i === index ? { ...row, [field]: value } : row)));
    const clave = `${index}-${field}`;
    const error = validarCampo(field, value);
    setErrores((prev) => {
      if (error === null) {
        if (!(clave in prev)) return prev;
        const siguiente = { ...prev };
        delete siguiente[clave];
        return siguiente;
      }
      return { ...prev, [clave]: error };
    });
  }

  const hayErrores = Object.keys(errores).length > 0;

  async function handleSave() {
    if (hayErrores) {
      toast.error("Corrige los campos marcados en rojo antes de guardar.");
      return;
    }
    setSaving(true);
    try {
      const stockMinimoByCategoria = Object.fromEntries(
        Object.entries(stockActualByCategoria).map(([code, row]) => [code, row.stock_minimo]),
      );
      const result = await saveIngestRows(fecha, rows, stockMinimoByCategoria);
      if (result.ventasGuardadas > 0) {
        toast.success(
          `${result.ventasGuardadas} registro(s) de venta guardados para el ${formatFecha(fecha)}.`,
        );
      }
      if (result.stockActualizado > 0) {
        toast.success(`Stock actualizado en ${result.stockActualizado} categoría(s).`);
      }
      for (const reason of result.erroresVentas) {
        toast.warning(reason);
      }
      if (result.ventasGuardadas === 0 && result.stockActualizado === 0) {
        toast.info("No hay filas completas para guardar.");
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        toast.error("Se requiere rol de administrador para cargar datos.");
      } else {
        toast.error(describeError(err, "No se pudieron guardar los registros."));
      }
    } finally {
      setSaving(false);
    }
  }

  function celda(index: number, field: Campo) {
    const clave = `${index}-${field}`;
    return errores[clave];
  }

  return (
    <div className="space-y-4">
      <div>
        <label htmlFor="fechaIngesta" className="mb-1.5 block text-xs font-medium text-slate-500">
          Fecha del registro
        </label>
        <input
          id="fechaIngesta"
          type="date"
          value={fecha}
          onChange={(e) => setFecha(e.target.value)}
          className={inputClass}
        />
      </div>

      <div className={`${cardClass} overflow-hidden`}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/80 text-left text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
                <th className="px-4 py-2.5 font-semibold">Categoría</th>
                <th className="px-4 py-2.5 font-semibold">Cantidad vendida</th>
                <th className="px-4 py-2.5 font-semibold">Precio medio</th>
                <th className="px-4 py-2.5 font-semibold">Stock actual</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row, index) => {
                const label =
                  CLASIFICADORES.find((c) => c.code === row.clasificador)?.label ??
                  row.clasificador;
                const errorCantidad = celda(index, "cantidadVendida");
                const errorPrecio = celda(index, "precioMedio");
                const errorStock = celda(index, "stockActual");
                return (
                  <tr key={row.clasificador} className="transition-colors hover:bg-slate-50/60">
                    <td className="px-4 py-2 font-medium whitespace-nowrap text-slate-700">
                      {label}
                    </td>
                    <td className="px-4 py-2">
                      <input
                        type="number"
                        min="0"
                        step="1"
                        value={row.cantidadVendida}
                        onChange={(e) => updateRow(index, "cantidadVendida", e.target.value)}
                        placeholder="0"
                        className={`${inputClass} w-24 px-2.5 py-1.5 text-right font-mono tabular-nums ${
                          errorCantidad ? "border-red-400 focus:ring-red-400/40" : ""
                        }`}
                      />
                      {errorCantidad && <p className="mt-1 text-[11px] text-red-600">{errorCantidad}</p>}
                    </td>
                    <td className="px-4 py-2">
                      <div className="relative w-28">
                        <span className="pointer-events-none absolute inset-y-0 left-2.5 flex items-center text-slate-400">
                          $
                        </span>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={row.precioMedio}
                          onChange={(e) => updateRow(index, "precioMedio", e.target.value)}
                          placeholder="0.00"
                          className={`${inputClass} w-full py-1.5 pr-2.5 pl-6 text-right font-mono tabular-nums ${
                            errorPrecio ? "border-red-400 focus:ring-red-400/40" : ""
                          }`}
                        />
                      </div>
                      {errorPrecio && <p className="mt-1 text-[11px] text-red-600">{errorPrecio}</p>}
                    </td>
                    <td className="px-4 py-2">
                      <input
                        type="number"
                        min="0"
                        step="1"
                        value={row.stockActual}
                        onChange={(e) => updateRow(index, "stockActual", e.target.value)}
                        placeholder="0"
                        className={`${inputClass} w-24 px-2.5 py-1.5 text-right font-mono tabular-nums ${
                          errorStock ? "border-red-400 focus:ring-red-400/40" : ""
                        }`}
                      />
                      {errorStock && <p className="mt-1 text-[11px] text-red-600">{errorStock}</p>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <button onClick={handleSave} disabled={saving || hayErrores} className={btnPrimary}>
        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
        {saving ? "Guardando…" : "Guardar cambios"}
      </button>
    </div>
  );
}
