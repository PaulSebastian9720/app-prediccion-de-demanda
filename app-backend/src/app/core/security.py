"""Primitivas de seguridad: hashing de contrasenas, JWT y refresh tokens."""

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import Settings
from app.core.exceptions import InvalidTokenError, TokenExpiredError

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Genera un hash Argon2id de la contrasena en texto plano."""
    return _password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verifica una contrasena en texto plano contra su hash Argon2id."""
    try:
        return _password_hasher.verify(hashed, password)
    except VerifyMismatchError:
        return False


def create_access_token(
    *, subject: str, role: str, settings: Settings, expires_delta: timedelta | None = None
) -> str:
    """Crea un JWT de acceso (stateless, HS256) para el usuario `subject`."""
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(
        payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    """Decodifica y valida un JWT de acceso. Levanta excepciones de dominio si es invalido."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError() from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError() from exc

    if payload.get("type") != "access":
        raise InvalidTokenError()
    return payload


def generate_refresh_token() -> tuple[str, str]:
    """Genera un refresh token opaco y su hash SHA-256 (el hash es lo unico que se persiste)."""
    raw_token = secrets.token_urlsafe(64)
    token_hash = hash_refresh_token(raw_token)
    return raw_token, token_hash


def hash_refresh_token(raw_token: str) -> str:
    """Calcula el hash SHA-256 (hex) de un refresh token en texto plano."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def verify_refresh_token_hash(raw_token: str, stored_hash: str) -> bool:
    """Compara un refresh token recibido contra su hash almacenado, en tiempo constante."""
    return hmac.compare_digest(hash_refresh_token(raw_token), stored_hash)
