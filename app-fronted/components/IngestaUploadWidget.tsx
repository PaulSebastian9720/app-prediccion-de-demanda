"use client";

// Carga masiva por archivo (CSV/XLSX) de ventas o stock, con plantilla
// descargable -- alternativa a llenar la tabla manual fila por fila. Zona de
// arrastrar-y-soltar con vista previa del archivo elegido y un paso de
// confirmacion explicito antes de subir (no se sube solo con elegir el
// archivo). El backend valida fila por fila y devuelve `errors` para las que
// rechaza, sin abortar el archivo completo por una fila mala.

import { useRef, useState } from "react";
import { CheckCircle2, Download, FileUp, Loader2, Upload, X } from "lucide-react";
import { toast } from "sonner";
import {
  downloadSalesTemplate,
  downloadStockTemplate,
  uploadSalesFile,
  uploadStockFile,
  type BulkUpsertResponse,
} from "@/lib/api-inventory";
import { ApiError } from "@/lib/api";
import { btnPrimary, btnSecondary, cardClass, describeError } from "@/lib/ui";

interface TipoIngesta {
  key: "ventas" | "stock";
  titulo: string;
  columnas: string;
  upload: (file: File) => Promise<BulkUpsertResponse>;
  descargarPlantilla: () => Promise<void>;
}

const TIPOS: TipoIngesta[] = [
  {
    key: "ventas",
    titulo: "Ventas",
    columnas: "clasificador, dia, cantidad_vendida, precio_medio",
    upload: uploadSalesFile,
    descargarPlantilla: downloadSalesTemplate,
  },
  {
    key: "stock",
    titulo: "Stock",
    columnas: "clasificador, stock_actual, stock_minimo",
    upload: uploadStockFile,
    descargarPlantilla: downloadStockTemplate,
  },
];

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

export function IngestaUploadWidget() {
  return (
    <div className={`${cardClass} space-y-4 p-4 sm:p-5`}>
      <div>
        <h3 className="text-sm font-semibold text-slate-700">Carga masiva por archivo</h3>
        <p className="mt-1 text-xs text-slate-500">
          Formatos aceptados: .csv y .xlsx. Alternativa a llenar la tabla fila por fila.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {TIPOS.map((tipo) => (
          <UploadCard key={tipo.key} tipo={tipo} />
        ))}
      </div>
    </div>
  );
}

function UploadCard({ tipo }: { tipo: TipoIngesta }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [resultado, setResultado] = useState<BulkUpsertResponse | null>(null);

  function elegirArchivo(file: File | undefined) {
    if (!file) return;
    setSelectedFile(file);
    setResultado(null);
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    elegirArchivo(e.target.files?.[0]);
    e.target.value = "";
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    elegirArchivo(e.dataTransfer.files?.[0]);
  }

  async function handleConfirmarCarga() {
    if (!selectedFile) return;
    setUploading(true);
    try {
      const result = await tipo.upload(selectedFile);
      setResultado(result);
      setSelectedFile(null);
      if (result.rows_upserted > 0) {
        toast.success(`${result.rows_upserted} fila(s) de ${tipo.titulo.toLowerCase()} cargadas.`);
      }
      if (result.rows_rejected > 0) {
        toast.warning(`${result.rows_rejected} fila(s) rechazadas -- ver detalle abajo.`);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        toast.error("Se requiere rol de administrador para cargar archivos.");
      } else {
        toast.error(describeError(err, `No se pudo cargar el archivo de ${tipo.titulo.toLowerCase()}.`));
      }
    } finally {
      setUploading(false);
    }
  }

  async function handleDownloadTemplate() {
    try {
      await tipo.descargarPlantilla();
    } catch (err) {
      toast.error(describeError(err, "No se pudo descargar la plantilla."));
    }
  }

  return (
    <div className="space-y-3 rounded-lg border border-slate-200 p-3.5">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-medium text-slate-700">{tipo.titulo}</p>
          <p className="mt-0.5 text-[11px] text-slate-400">Columnas: {tipo.columnas}</p>
        </div>
        <button type="button" onClick={handleDownloadTemplate} className={btnSecondary}>
          <Download className="h-3.5 w-3.5" />
          Plantilla
        </button>
      </div>

      {selectedFile ? (
        <div className="flex items-center justify-between gap-2 rounded-lg border border-accent-200 bg-accent-50 px-3 py-2.5">
          <div className="flex min-w-0 items-center gap-2">
            <FileUp className="h-4 w-4 shrink-0 text-accent-600" />
            <div className="min-w-0">
              <p className="truncate text-xs font-medium text-slate-700">{selectedFile.name}</p>
              <p className="text-[11px] text-slate-500">{formatBytes(selectedFile.size)}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setSelectedFile(null)}
            disabled={uploading}
            className="shrink-0 rounded-md p-1 text-slate-400 transition hover:bg-slate-200/60 hover:text-slate-600 disabled:opacity-50"
            aria-label="Quitar archivo"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ) : (
        <div
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={`flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-lg border-2 border-dashed px-3 py-6 text-center transition-colors ${
            dragOver
              ? "border-accent-400 bg-accent-50"
              : "border-slate-200 bg-slate-50/60 hover:border-slate-300 hover:bg-slate-50"
          }`}
        >
          <Upload className="h-5 w-5 text-slate-400" />
          <p className="text-xs font-medium text-slate-600">Arrastra tu archivo aquí</p>
          <p className="text-[11px] text-slate-400">o haz clic para elegirlo</p>
        </div>
      )}
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.xlsx"
        className="hidden"
        onChange={handleInputChange}
      />

      <button
        type="button"
        onClick={handleConfirmarCarga}
        disabled={!selectedFile || uploading}
        className={`${btnPrimary} w-full`}
      >
        {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileUp className="h-3.5 w-3.5" />}
        {uploading ? "Subiendo…" : "Confirmar carga"}
      </button>

      {resultado && (
        <div className="rounded-md bg-slate-50 px-2.5 py-2 text-xs text-slate-600">
          <p className="flex items-center gap-1.5">
            {resultado.rows_rejected === 0 && (
              <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-600" />
            )}
            {resultado.rows_upserted} de {resultado.rows_received} fila(s) cargadas
            {resultado.rows_rejected > 0 && `, ${resultado.rows_rejected} rechazada(s)`}.
          </p>
          {resultado.errors.length > 0 && (
            <ul className="mt-1.5 list-disc space-y-0.5 pl-4 text-red-600">
              {resultado.errors.map((e, i) => (
                <li key={i}>
                  Fila {e.row + 1}: {e.reason}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
