// Cliente HTTP para el backend real (app-backend). Adjunta el access token
// guardado, y si una respuesta llega en 401 intenta refrescar el token una
// vez (POST /auth/refresh) y reintenta la solicitud original antes de
// rendirse y mandar al usuario de vuelta a /login.

import { clearAuth, getStoredAuth, updateStoredTokens } from "./auth";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

interface BackendErrorBody {
  error?: { code: string; message: string; details?: unknown };
}

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function parseErrorBody(response: Response): Promise<BackendErrorBody | null> {
  try {
    return (await response.json()) as BackendErrorBody;
  } catch {
    return null;
  }
}

let refreshPromise: Promise<boolean> | null = null;

async function tryRefreshToken(): Promise<boolean> {
  const stored = getStoredAuth();
  if (!stored) return false;

  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: stored.refreshToken }),
        });
        if (!res.ok) return false;
        const data = (await res.json()) as { access_token: string; refresh_token: string };
        updateStoredTokens(data.access_token, data.refresh_token);
        return true;
      } catch {
        return false;
      } finally {
        refreshPromise = null;
      }
    })();
  }
  return refreshPromise;
}

interface RequestOptions extends RequestInit {
  skipAuthRetry?: boolean;
}

async function request(path: string, options: RequestOptions = {}): Promise<Response> {
  const stored = getStoredAuth();
  const headers = new Headers(options.headers);
  if (stored?.accessToken) {
    headers.set("Authorization", `Bearer ${stored.accessToken}`);
  }
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (response.status === 401 && !options.skipAuthRetry && stored) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      return request(path, { ...options, headers: options.headers, skipAuthRetry: true });
    }
    clearAuth();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  }

  return response;
}

export async function apiJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await request(path, options);
  if (!response.ok) {
    const body = await parseErrorBody(response);
    throw new ApiError(
      response.status,
      body?.error?.message ?? response.statusText,
      body?.error?.code,
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function apiBlob(
  path: string,
  options: RequestOptions = {},
): Promise<{ blob: Blob; filename: string | null }> {
  const response = await request(path, options);
  if (!response.ok) {
    const body = await parseErrorBody(response);
    throw new ApiError(
      response.status,
      body?.error?.message ?? response.statusText,
      body?.error?.code,
    );
  }
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition");
  const match = disposition?.match(/filename="?([^"]+)"?/);
  return { blob, filename: match?.[1] ?? null };
}
