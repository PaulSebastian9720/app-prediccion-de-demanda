// Encabezado de titulo + descripcion, compartido por las 4 paginas del dashboard.

export function SectionHeader({ title, description }: { title: string; description: string }) {
  return (
    <div>
      <h2 className="text-lg font-semibold tracking-tight text-slate-900">{title}</h2>
      <p className="mt-1 max-w-prose text-sm text-slate-500">{description}</p>
    </div>
  );
}
