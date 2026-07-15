"""Instancia compartida del rate limiter (`slowapi`, en memoria, sin Redis).

Se define en un modulo aparte (en vez de crearla en `main.py`) para poder
importarla tanto en el middleware global (`SlowAPIMiddleware`, limite por
defecto) como en rutas especificas que necesitan un limite mas estricto
(`@limiter.limit(...)` en `/auth/login`).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

limiter = Limiter(key_func=get_remote_address, default_limits=[get_settings().rate_limit_default])
