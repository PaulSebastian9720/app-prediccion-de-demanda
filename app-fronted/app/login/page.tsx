"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, LineChart, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { fetchCurrentUser, login } from "@/lib/api-auth";
import { ApiError } from "@/lib/api";
import { storeAuth } from "@/lib/auth";

const inputClass =
  "w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-900 shadow-xs transition outline-none placeholder:text-slate-400 focus:border-accent-400 focus:ring-4 focus:ring-accent-500/10";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!email.trim() || !password.trim()) {
      setError("Ingresa tu correo y contraseña.");
      return;
    }

    setError(null);
    setLoading(true);
    try {
      const tokens = await login(email.trim(), password);
      const user = await fetchCurrentUser(tokens.access_token);
      storeAuth({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token, user });
      toast.success("Sesión iniciada");
      router.push("/");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Correo o contraseña incorrectos.");
      } else {
        setError("No se pudo conectar con el backend. Verifica que esté corriendo.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-dvh flex-1 items-center justify-center overflow-hidden px-4 py-10">
      {/* Gradientes ambientales suaves detras de la tarjeta */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(600px 320px at 18% 8%, rgb(69 82 165 / 0.08), transparent 65%)," +
            "radial-gradient(520px 300px at 85% 90%, rgb(69 82 165 / 0.07), transparent 65%)",
        }}
      />

      <div className="relative w-full max-w-sm">
        <div className="mb-6 flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-600 shadow-card">
            <LineChart className="h-4.5 w-4.5 text-white" strokeWidth={2.25} />
          </span>
          <div className="leading-tight">
            <p className="text-sm font-semibold tracking-tight text-slate-900">Ventas Forecast</p>
            <p className="text-xs text-slate-500">Predicción de demanda</p>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card sm:p-8">
          <h1 className="text-lg font-semibold tracking-tight text-slate-900">Iniciar sesión</h1>
          <p className="mt-1 text-sm text-slate-500">Accede al panel de reabastecimiento.</p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div>
              <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-slate-700">
                Correo
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@example.com"
                className={inputClass}
              />
            </div>

            <div>
              <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-slate-700">
                Contraseña
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className={inputClass}
              />
            </div>

            {error && (
              <div className="flex items-start gap-2 rounded-lg border border-red-100 bg-red-50 px-3 py-2.5 text-sm text-red-700">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent-600 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-accent-700 active:scale-[0.99] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500/50 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              {loading ? "Ingresando…" : "Ingresar"}
            </button>
          </form>
        </div>

        <p className="mt-6 text-center text-xs text-slate-400">
          Ventas Forecast API · panel interno de reabastecimiento
        </p>
      </div>
    </div>
  );
}
