"""Cabeceras de seguridad basicas y limite de tamano de body (proteccion tipo gateway)."""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Agrega cabeceras de seguridad basicas a toda respuesta."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Rechaza (413) requests cuyo `Content-Length` supere el limite configurado."""

    def __init__(self, app: ASGIApp, max_body_size: int) -> None:
        super().__init__(app)
        self._max_body_size = max_body_size

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > self._max_body_size:
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": "PAYLOAD_TOO_LARGE",
                        "message": (
                            f"El cuerpo de la solicitud excede el limite de "
                            f"{self._max_body_size} bytes."
                        ),
                        "details": None,
                    }
                },
            )
        return await call_next(request)
