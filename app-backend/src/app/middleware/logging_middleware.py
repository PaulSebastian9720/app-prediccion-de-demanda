"""Middleware que loggea cada request a consola y agenda su persistencia en `request_logs`."""

import contextlib
import logging
import time
import uuid

from starlette.background import BackgroundTask, BackgroundTasks
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.services.log_service import create_request_log

logger = logging.getLogger("app.requests")


def _extract_user_id(request: Request) -> uuid.UUID | None:
    """Extrae el `sub` del JWT sin fallar si el header falta o el token es invalido.

    Es solo para enriquecer el log de auditoria: nunca debe bloquear la
    request (la validacion real de auth ocurre en `api.deps.get_current_user`).
    """
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header.split(" ", 1)[1]
    with contextlib.suppress(Exception):
        payload = decode_access_token(token, get_settings())
        return uuid.UUID(payload["sub"])
    return None


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Mide duracion, loggea a consola y adjunta un `BackgroundTask` para persistir en BD."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        user_id = _extract_user_id(request)
        ip_address = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent")

        logger.info(
            "%s %s -> %s (%.2fms) ip=%s user=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            ip_address,
            user_id or "-",
        )

        persist_task = BackgroundTask(
            create_request_log,
            request.app.state.session_factory,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # No se pisa un BackgroundTask que el endpoint ya haya asignado a la
        # respuesta: se encadenan ambos en un `BackgroundTasks` (plural).
        if response.background is not None:
            tasks = BackgroundTasks()
            existing = response.background
            if isinstance(existing, BackgroundTasks):
                tasks.tasks.extend(existing.tasks)
            else:
                tasks.tasks.append(existing)
            tasks.add_task(
                create_request_log,
                request.app.state.session_factory,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            response.background = tasks
        else:
            response.background = persist_task

        return response
