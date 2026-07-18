"use client";

// La raiz del sitio no tiene contenido propio: solo decide a donde mandar
// segun haya o no sesion guardada. El dashboard real vive en sus propias
// paginas bajo `app/(dashboard)/*` (predicciones, reportes, ingesta, historial).

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { getStoredAuth } from "@/lib/auth";

export default function RootPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace(getStoredAuth() ? "/predicciones" : "/login");
  }, [router]);

  return (
    <div className="flex min-h-dvh flex-1 items-center justify-center">
      <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
    </div>
  );
}
