"""Configuracion centralizada de la aplicacion, cargada desde variables de entorno / .env."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracion global de la aplicacion.

    Todos los valores tienen defaults seguros para desarrollo local. En
    produccion, `jwt_secret_key` y las credenciales de base de datos deben
    sobreescribirse via variables de entorno reales (nunca el `.env` de ejemplo).
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Aplicacion
    app_name: str = "Ventas Forecast API"
    app_env: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    # Colorea los logs de consola con codigos ANSI (se ven tal cual en
    # `docker compose logs`). Poner en false para logs planos (CI, ficheros).
    log_colors: bool = True
    # Echo de cada sentencia SQL de SQLAlchemy a consola. Independiente de
    # `debug`: es MUY verboso (varias lineas por request), por eso va aparte y
    # apagado por defecto, para que la narrativa del pipeline no quede sepultada.
    db_echo: bool = False

    # Base de datos
    database_url: str = (
        "postgresql+asyncpg://ventas_user:ventas_password@localhost:5432/ventas_forecast"
    )

    # JWT
    jwt_secret_key: SecretStr = SecretStr("dev-secret-change-me")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # CORS
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return list(v)

    # Rate limiting
    rate_limit_default: str = "100/minute"
    rate_limit_auth: str = "5/minute"

    # Modelo ML
    model_artifacts_dir: Path = Path("artifacts")

    # Seguridad
    max_body_size_bytes: int = 2_000_000

    # Admin inicial (usado por scripts/create_admin.py)
    initial_admin_email: str = "admin@example.com"
    initial_admin_password: str = "change-this-password"

    # LLM (resumen ejecutivo de los reportes PDF y explicacion de predicciones diarias)
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"
    # Tope de espera para la llamada de explicacion de /predictions/day: si se
    # excede (o falla por cualquier motivo), se degrada a la plantilla
    # deterministica en vez de bloquear la respuesta al cliente.
    llm_explanation_timeout_seconds: float = 4.0

    # Reportes PDF
    report_logo_path: Path | None = None
    report_currency_symbol: str = "$"

    @field_validator("openai_api_key", "report_logo_path", mode="before")
    @classmethod
    def _blank_env_value_to_none(cls, v: str | None) -> str | None:
        """Una env var vacia (`REPORT_LOGO_PATH=`) debe leerse como "no configurado",
        no como cadena vacia / `Path("")` (que resuelve al directorio actual)."""
        if isinstance(v, str) and not v.strip():
            return None
        return v


@lru_cache
def get_settings() -> Settings:
    """Singleton de `Settings`, cacheado para leer `.env` una sola vez por proceso."""
    return Settings()
