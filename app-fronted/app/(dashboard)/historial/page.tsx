import { PredictionHistoryTable } from "@/components/PredictionHistoryTable";
import { SectionHeader } from "@/components/SectionHeader";

export default function HistorialPage() {
  return (
    <section className="space-y-6">
      <SectionHeader
        title="Historial de predicciones"
        description="Predicciones pasadas de un día específico, con la explicación guardada de por qué se llegó a ese resultado."
      />
      <PredictionHistoryTable />
    </section>
  );
}
