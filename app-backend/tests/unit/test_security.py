"""Tests unitarios de primitivas de seguridad: hashing, JWT, refresh tokens."""

from datetime import timedelta

import pytest

from app.core.config import Settings
from app.core.exceptions import InvalidTokenError, TokenExpiredError
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
    verify_refresh_token_hash,
)


@pytest.fixture
def settings() -> Settings:
    return Settings(jwt_secret_key="test-secret")


def test_hash_password_and_verify_roundtrip() -> None:
    hashed = hash_password("MiPassword123")
    assert hashed != "MiPassword123"
    assert verify_password("MiPassword123", hashed)
    assert not verify_password("otra-password", hashed)


def test_create_and_decode_access_token(settings: Settings) -> None:
    token = create_access_token(subject="user-id-1", role="user", settings=settings)
    payload = decode_access_token(token, settings)
    assert payload["sub"] == "user-id-1"
    assert payload["role"] == "user"
    assert payload["type"] == "access"


def test_decode_expired_token_raises(settings: Settings) -> None:
    token = create_access_token(
        subject="user-id-1", role="user", settings=settings, expires_delta=timedelta(seconds=-1)
    )
    with pytest.raises(TokenExpiredError):
        decode_access_token(token, settings)


def test_decode_garbage_token_raises(settings: Settings) -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token("not-a-real-token", settings)


def test_generate_refresh_token_and_verify_hash() -> None:
    raw, token_hash = generate_refresh_token()
    assert raw != token_hash
    assert verify_refresh_token_hash(raw, token_hash)
    assert not verify_refresh_token_hash("another-token", token_hash)
    assert hash_refresh_token(raw) == token_hash
