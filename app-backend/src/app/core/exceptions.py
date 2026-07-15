"""Excepciones de dominio de la aplicacion.

Todas heredan de `AppException` y se traducen a una respuesta JSON consistente
`{"error": {"code", "message", "details"}}` por un unico exception handler
(ver `app.middleware.exception_handlers`).
"""

from typing import Any


class AppException(Exception):
    """Excepcion base de dominio."""

    code: str = "APP_ERROR"
    status_code: int = 500

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details
        super().__init__(message)


class NotFoundError(AppException):
    code = "NOT_FOUND"
    status_code = 404


class ConflictError(AppException):
    code = "CONFLICT"
    status_code = 409


class UnauthorizedError(AppException):
    code = "UNAUTHORIZED"
    status_code = 401


class ForbiddenError(AppException):
    code = "FORBIDDEN"
    status_code = 403


class InvalidCredentialsError(UnauthorizedError):
    code = "INVALID_CREDENTIALS"

    def __init__(self) -> None:
        super().__init__("Correo o contrasena incorrectos.")


class TokenExpiredError(UnauthorizedError):
    code = "TOKEN_EXPIRED"

    def __init__(self) -> None:
        super().__init__("El token ha expirado.")


class InvalidTokenError(UnauthorizedError):
    code = "INVALID_TOKEN"

    def __init__(self) -> None:
        super().__init__("El token es invalido.")


class TokenRevokedError(UnauthorizedError):
    code = "TOKEN_REVOKED"

    def __init__(self) -> None:
        super().__init__("El refresh token fue revocado o ya fue usado.")


class InsufficientHistoryError(AppException):
    code = "INSUFFICIENT_HISTORY"
    status_code = 422


class InvalidFileError(AppException):
    code = "INVALID_FILE"
    status_code = 422


class UnknownClassifierError(AppException):
    code = "UNKNOWN_CLASSIFIER"
    status_code = 422


class ModelNotLoadedError(AppException):
    code = "MODEL_NOT_LOADED"
    status_code = 503

    def __init__(self) -> None:
        super().__init__("El modelo de prediccion todavia no esta cargado.")


class DateTooFarError(AppException):
    code = "DATE_TOO_FAR"
    status_code = 422


class InsufficientTrainingDataError(AppException):
    code = "INSUFFICIENT_TRAINING_DATA"
    status_code = 422
