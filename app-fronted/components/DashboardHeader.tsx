"use client";

// Header + navegacion compartidos por las 4 paginas del dashboard
// (Predicciones, Reportes, Datos y Modelo, Historial). Cada seccion es su
// propia ruta -- este header vive en `app/(dashboard)/layout.tsx`, no en
// cada pagina.

import type { ComponentType } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Database, FileText, History, LineChart, LogOut, TrendingUp } from "lucide-react";
import { btnSecondary } from "@/lib/ui";

const NAV_ITEMS: { href: string; label: string; icon: ComponentType<{ className?: string }> }[] = [
  { href: "/predicciones", label: "Predicciones", icon: TrendingUp },
  { href: "/reportes", label: "Reportes", icon: FileText },
  { href: "/datos", label: "Datos y Modelo", icon: Database },
  { href: "/historial", label: "Historial", icon: History },
];

export function DashboardHeader({
  userEmail,
  onLogout,
}: {
  userEmail: string;
  onLogout: () => void;
}) {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/85 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3.5 sm:px-6">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-600 shadow-sm">
            <LineChart className="h-4 w-4 text-white" strokeWidth={2.25} />
          </span>
          <span className="text-base font-semibold tracking-tight text-slate-900">
            Ventas Forecast
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="hidden rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600 sm:inline-block">
            {userEmail}
          </span>
          <button onClick={onLogout} className={btnSecondary}>
            <LogOut className="h-3.5 w-3.5" />
            Salir
          </button>
        </div>
      </div>

      <nav className="mx-auto flex max-w-6xl gap-1 px-4 sm:px-6">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`relative flex items-center gap-1.5 px-3 py-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500/40 ${
                active ? "text-accent-700" : "text-slate-500 hover:text-slate-800"
              }`}
            >
              <Icon className="h-4 w-4" />
              {label}
              {active && (
                <span className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-accent-600" />
              )}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
