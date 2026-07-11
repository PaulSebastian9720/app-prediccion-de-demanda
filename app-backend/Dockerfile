# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    # Librerias de sistema requeridas por WeasyPrint (genera los reportes PDF):
    # Pango/Cairo para el layout y render de texto, GDK-Pixbuf para imagenes
    # embebidas (logo, graficas), libffi para los bindings de cffi.
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libcairo2 \
    libffi-dev \
    shared-mime-info \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Instala dependencias primero (aprovecha la cache de capas de Docker)
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --no-dev

# Copia el codigo de la aplicacion
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY artifacts/ ./artifacts/
COPY scripts/ ./scripts/
COPY entrypoint.sh ./

RUN uv sync --frozen --no-dev && chmod +x entrypoint.sh

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
