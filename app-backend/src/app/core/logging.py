"""Configuracion del logging a consola, con colores ANSI opcionales.

Ademas de colorear cada linea por nivel (DEBUG/INFO/WARNING/...), expone
`paint()` para que otros modulos (p.ej. el pipeline de prediccion en
`app.services.prediction_service`) coloreen partes concretas del mensaje por
categoria semantica: azul=acceso a datos/BD, cian=preparacion de features,
magenta=el modelo entrenado, verde=resultado. Los codigos ANSI se ven tal cual
en `docker compose logs` (los interpreta la terminal, no hace falta TTY).
"""

import logging
import logging.config

from app.core.config import Settings

# --- Paleta ANSI -----------------------------------------------------------
_RESET = "\033[0m"
_BOLD = "\033[1m"
_ANSI = {
    "gray": "\033[90m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[97m",
}

# Se fija en configure_logging(). Por defecto sin color, para que importar el
# modulo (p.ej. en tests) no emita codigos ANSI antes de configurar nada.
_colors_enabled = False


def paint(text: str, color: str, *, bold: bool = False) -> str:
    """Envuelve `text` en el color ANSI dado.

    Devuelve el texto sin tocar si los colores estan desactivados
    (`settings.log_colors=false`, o antes de llamar a `configure_logging`), de
    modo que quien lo use no tiene que preocuparse por el modo sin color.
    """
    if not _colors_enabled:
        return text
    code = _ANSI.get(color, "")
    if bold:
        code = _BOLD + code
    return f"{code}{text}{_RESET}"


_LEVEL_COLORS = {
    "DEBUG": "gray",
    "INFO": "cyan",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "red",
}


class _ColorFormatter(logging.Formatter):
    """Colorea el nivel y atenua timestamp + nombre del logger.

    El cuerpo del mensaje se deja intacto: si ya trae colores propios (via
    `paint()`), conviven con el color por nivel sin pisarse.
    """

    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record)
        level = f"{record.levelname:<8}"
        name = record.name
        message = record.getMessage()

        if record.exc_info:
            message = f"{message}\n{self.formatException(record.exc_info)}"

        if not _colors_enabled:
            return f"{ts} | {level} | {name} | {message}"

        level_color = _LEVEL_COLORS.get(record.levelname, "white")
        sep = paint("│", "gray")
        return (
            f"{paint(ts, 'gray')} {sep} "
            f"{paint(level, level_color, bold=True)} {sep} "
            f"{paint(name, 'gray')} {sep} {message}"
        )


def configure_logging(settings: Settings) -> None:
    """Configura el logging a stdout para toda la aplicacion.

    Se invoca una sola vez, al arrancar `create_app()`. `settings.log_colors`
    activa los colores ANSI (visibles en `docker compose logs`). El nivel de
    `uvicorn.access` y `sqlalchemy.engine` se silencia a WARNING salvo en modo
    debug, para no inundar la consola con ruido de bajo nivel.
    """
    global _colors_enabled
    _colors_enabled = settings.log_colors

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "console": {"()": _ColorFormatter},
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "console",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "handlers": ["console"],
                "level": settings.log_level,
            },
            "loggers": {
                "uvicorn.access": {"level": "INFO" if settings.debug else "WARNING"},
                # El SQL crudo se controla con `db_echo` (no con `debug`): es tan
                # verboso que, si no, entierra la narrativa del pipeline de ML.
                "sqlalchemy.engine": {"level": "INFO" if settings.db_echo else "WARNING"},
            },
        }
    )
