// Clases Tailwind compartidas por todas las secciones del dashboard: un solo
// acento, foco visible y feedback al presionar.

import { ApiError } from "./api";

export const btnPrimary =
  "inline-flex items-center justify-center gap-2 rounded-lg bg-accent-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-accent-700 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500/50 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60";

export const btnSecondary =
  "inline-flex items-center justify-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 shadow-xs transition hover:bg-slate-50 hover:text-slate-900 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500/40 disabled:cursor-not-allowed disabled:opacity-60";

export const inputClass =
  "rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-xs transition outline-none placeholder:text-slate-400 focus:border-accent-400 focus:ring-4 focus:ring-accent-500/10";

export const cardClass = "rounded-xl border border-slate-200/80 bg-white shadow-card";

export function describeError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.message;
  return fallback;
}
