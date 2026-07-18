"use client";

// Pagina "Datos y Modelo": cargar datos nuevos (manual o por archivo) y
// reentrenar el modelo con ellos -- un solo lugar, porque el flujo natural es
// subir datos -> reentrenar, no dos pantallas separadas.

import { IngestaManualTable } from "@/components/IngestaManualTable";
import { IngestaUploadWidget } from "@/components/IngestaUploadWidget";
import { RetrainingPanel } from "@/components/RetrainingPanel";
import { SectionHeader } from "@/components/SectionHeader";

export function DatosYModeloSection() {
  return (
    <section className="space-y-6">
      <SectionHeader
        title="Datos y Modelo"
        description="Carga ventas/stock nuevos y reentrena el modelo con ellos."
      />

      <IngestaManualTable />
      <IngestaUploadWidget />
      <RetrainingPanel />
    </section>
  );
}
