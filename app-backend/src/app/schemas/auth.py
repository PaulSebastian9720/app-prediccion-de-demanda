"""Schemas de autenticacion: registro, login, refresh, logout."""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Datos requeridos para registrar un nuevo usuario."""

    email: EmailStr = Field(..., examples=["usuario@example.com"])
    password: str = Field(..., min_length=8, max_length=128, examples=["ContraseñaSegura123"])
    full_name: str | None = Field(default=None, max_length=255, examples=["Ana Perez"])


class LoginRequest(BaseModel):
    """Credenciales de acceso."""

    email: EmailStr = Field(..., examples=["usuario@example.com"])
    password: str = Field(..., min_length=1, examples=["ContraseñaSegura123"])


class TokenResponse(BaseModel):
    """Par de tokens emitido en login/refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Segundos hasta la expiracion del access_token.")


class RefreshRequest(BaseModel):
    """Solicitud de rotacion de tokens."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Solicitud de cierre de sesion (revoca un refresh token especifico)."""

    refresh_token: str
