// Autenticacion real contra POST /auth/login, GET /auth/me y POST /auth/logout.

import { API_BASE_URL, apiJson } from "./api";
import type { AuthUser } from "./auth";

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  return apiJson<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

/** Se usa un fetch crudo (no `apiJson`) porque en este punto el token todavia
 * no esta guardado en localStorage: se acaba de recibir de /auth/login. */
export async function fetchCurrentUser(accessToken: string): Promise<AuthUser> {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok) {
    throw new Error("No se pudo obtener el perfil del usuario.");
  }
  return (await response.json()) as AuthUser;
}

export async function logoutRequest(refreshToken: string): Promise<void> {
  try {
    await apiJson("/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch {
    // Best-effort: si falla, la sesion local se limpia igual.
  }
}
