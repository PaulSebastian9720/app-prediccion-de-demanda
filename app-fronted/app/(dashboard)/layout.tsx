"use client";

// Layout compartido por las 4 paginas del dashboard (Predicciones, Reportes,
// Ingesta, Historial): valida la sesion una sola vez y renderiza el header +
// navegacion comun, para que cada `page.tsx` solo tenga que preocuparse de su
// propio contenido.

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { DashboardHeader } from "@/components/DashboardHeader";
import { logoutRequest } from "@/lib/api-auth";
import { clearAuth, getStoredAuth, type AuthUser } from "@/lib/auth";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    const stored = getStoredAuth();
    if (!stored) {
      router.replace("/login");
      return;
    }
    // localStorage solo existe en cliente: esta lectura no puede moverse
    // fuera del efecto ni evitarse con una condicion (es el primer render).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setUser(stored.user);
  }, [router]);

  async function handleLogout() {
    const stored = getStoredAuth();
    if (stored) await logoutRequest(stored.refreshToken);
    clearAuth();
    router.push("/login");
  }

  if (!user) {
    return (
      <div className="flex min-h-dvh flex-1 items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="min-h-dvh">
      <DashboardHeader userEmail={user.email} onLogout={handleLogout} />
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">{children}</main>
    </div>
  );
}
