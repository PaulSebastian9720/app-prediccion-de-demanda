// Persistencia local de la sesion real (JWT access + refresh token, mas el
// perfil devuelto por GET /auth/me). El backend es la unica fuente de verdad;
// aqui solo se cachea lo necesario para no tener que volver a loguear en
// cada recarga de pagina.

const STORAGE_KEY = "ventas_forecast_auth";

export interface AuthUser {
  id: string;
  email: string;
  full_name: string | null;
  role: "user" | "admin";
  is_active: boolean;
  created_at: string;
}

export interface StoredAuth {
  accessToken: string;
  refreshToken: string;
  user: AuthUser;
}

export function getStoredAuth(): StoredAuth | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredAuth;
  } catch {
    return null;
  }
}

export function storeAuth(auth: StoredAuth): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(auth));
}

export function updateStoredTokens(accessToken: string, refreshToken: string): void {
  const current = getStoredAuth();
  if (!current) return;
  storeAuth({ ...current, accessToken, refreshToken });
}

export function clearAuth(): void {
  window.localStorage.removeItem(STORAGE_KEY);
}

export function isAdmin(user: AuthUser | null | undefined): boolean {
  return user?.role === "admin";
}
