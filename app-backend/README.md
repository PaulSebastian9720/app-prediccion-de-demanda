# Ventas Forecast API

Backend FastAPI de produccion que sirve un modelo XGBoost de forecasting de ventas
por categoria de producto (puerto fiel del pipeline de `notebooks/03_prediccion.ipynb`),
con autenticacion JWT completa (access + refresh token con rotacion), predicciones
dia/semana/mes/"dia X" con respaldo automatico por huecos de calendario, reportes
PDF de reabastecimiento con resumen ejecutivo por LLM, ingesta de historico de
ventas (JSON/CSV/XLSX/XML) y logging dual (consola + PostgreSQL, con trazabilidad
granular por etapa del pipeline de inferencia).

## Stack

Python 3.12+ · FastAPI · uv · Pydantic v2 · SQLAlchemy 2.x (async) · Alembic ·
PostgreSQL 17 · Ruff · MyPy · pytest · Locust · Docker / Docker Compose ·
WeasyPrint + matplotlib (reportes PDF) · OpenAI `gpt-4o-mini` (resumen ejecutivo).

## Arquitectura (resumen)

```
src/app/
├── main.py           # create_app() factory + lifespan (carga el modelo una sola vez)
├── core/              # config, logging, security (JWT/Argon2), excepciones, rate limit
├── db/                # engine/sesiones async + modelos SQLAlchemy
├── schemas/           # Pydantic v2 (request/response de cada endpoint)
├── ml/                 # registry (carga de artefactos) + features (pipeline de inferencia)
├── utils/              # parsers de archivos (CSV/XLSX/XML)
├── services/           # logica de negocio (auth, users, sales_history, prediction, logs,
│                         products, inventory)
├── reports/             # generacion de reportes PDF (metrics, charts, LLM, plantilla, pdf_generator)
├── api/v1/             # rutas HTTP (delgadas, delegan a services/)
└── middleware/         # logging de requests, cabeceras de seguridad, exception handlers
```

El modelo (`xgboost_ventas.json`, `transformer_clasificador.pkl`, `feature_cols.pkl`,
`metadata_modelo.json`) se carga una unica vez al arrancar (`lifespan`, en un hilo
aparte via `asyncio.to_thread` para no bloquear el event loop) y se mantiene en
memoria durante toda la vida del proceso.

## Requisitos

- Python 3.12+ y [uv](https://docs.astral.sh/uv/)
- Docker + Docker Compose (para la base de datos, y opcionalmente para el backend)

## Arranque rapido (local, con uv)

```bash
cd app-backend
cp .env.example .env          # ajustar secretos si hace falta (incl. OPENAI_API_KEY, opcional)
make install                  # uv sync
docker compose up -d db       # o: make db-up   (usa el compose liviano de la raiz del proyecto)
make migrate                  # aplica las migraciones de Alembic
make seed                     # carga artifacts/dataset_diario_series_temporales.csv
make seed-catalog             # siembra precio/costo/stock inicial por categoria (para reportes)
make create-admin             # crea el usuario admin inicial (INITIAL_ADMIN_EMAIL/.._PASSWORD)
make dev                      # uvicorn --reload en http://localhost:8000
```

Para levantar **solo la base de datos** desde la raiz del proyecto (sin construir
nada del backend), usar el compose liviano en `../docker/compose.yml` — mismas
credenciales/puerto/volumen que `app-backend/docker-compose.yml`:

```bash
docker compose -f ../docker/compose.yml up -d
```

Documentacion interactiva (Swagger) en `http://localhost:8000/docs`.

## Arranque con Docker (backend + base de datos)

```bash
cd app-backend
cp .env.example .env
docker compose up -d --build   # o: make docker-up
```

El `entrypoint.sh` del contenedor aplica las migraciones automaticamente
(`alembic upgrade head`) antes de arrancar `uvicorn`. Falta correr el seed y
crear el admin una vez (pueden ejecutarse localmente con `uv run ...` apuntando
al Postgres expuesto en `localhost:5434`, o con `docker compose exec backend ...`).

## Variables de entorno

Ver `.env.example` para la lista completa y valores por defecto de desarrollo.
Los mas relevantes: `DATABASE_URL`, `JWT_SECRET_KEY` (cambiar en produccion),
`CORS_ORIGINS`, `RATE_LIMIT_DEFAULT`/`RATE_LIMIT_AUTH`, `MODEL_ARTIFACTS_DIR`,
`OPENAI_API_KEY`/`OPENAI_MODEL` (resumen ejecutivo del reporte; si se deja vacio
se usa un resumen por plantilla, sin LLM), `REPORT_LOGO_PATH`/`REPORT_CURRENCY_SYMBOL`.

## Comandos disponibles (`Makefile`)

| Comando | Descripcion |
|---|---|
| `make install` | `uv sync` |
| `make dev` | Servidor local con hot-reload |
| `make lint` | `ruff check` + `mypy` |
| `make format` | `ruff check --fix` + `ruff format` |
| `make test` | Suite completa (unit + integracion) con cobertura |
| `make test-unit` / `make test-integration` | Solo unitarios / solo integracion |
| `make migrate` | Aplica migraciones de Alembic |
| `make migrate-new name="mensaje"` | Genera una nueva migracion (autogenerate) |
| `make seed` | Carga el CSV historico en `sales_history` |
| `make seed-catalog` | Siembra `products`/`inventory_stock` (precio, costo, stock inicial) |
| `make create-admin` | Crea/promueve el usuario admin inicial |
| `make db-up` | Levanta solo Postgres via `../docker/compose.yml` |
| `make docker-build` / `make docker-up` / `make docker-down` / `make docker-logs` | Docker Compose |
| `make locust` | Prueba de carga headless (20 usuarios, 60s) |
| `make clean` | Borra caches (`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, cobertura) |

## Tests

`make test` levanta una base de datos de test (`<POSTGRES_DB>_test`) real contra
el Postgres de `docker compose`, corre las migraciones/esquema, ejecuta la suite
completa contra la app real (via ASGI, sin proceso HTTP) y reporta cobertura.
Los tests unitarios de `tests/unit/test_features.py` validan el pipeline de
features/inferencia contra los valores de referencia calculados en
`notebooks/03_prediccion.ipynb` (misma categoria/fecha, misma prediccion exacta).

## Autenticacion

`POST /auth/register`, `POST /auth/login` (devuelve `access_token` de 15 min +
`refresh_token` opaco de 7 dias), `POST /auth/refresh` (rota el refresh token,
el anterior queda revocado), `POST /auth/logout` / `POST /auth/logout-all`,
`GET /auth/me`. En Swagger, usar el boton "Authorize" pegando el `access_token`.

## Prediccion

`POST /predictions/day` (cualquier fecha con historial previo — si hay un hueco
de calendario entre el ultimo dato real y la fecha pedida, se rellena
automaticamente encadenando predicciones dia a dia, sin que el llamador tenga
que hacer nada), `POST /predictions/week` (7 dias acumulados), `POST
/predictions/range` (`dias` 1-90, generaliza `/week`), y `POST
/predictions/day-x` (el caso de uso "predecir el 20 de julio empezando desde
hoy": recibe solo `clasificador` + `fecha_objetivo`, decide el punto de partida
automaticamente, y devuelve EN LA MISMA RESPUESTA tanto `prediccion_individual`
—solo ese dia— como `prediccion_acumulada` —la suma de todo el periodo recorrido
desde hoy hasta esa fecha—, ademas del desglose diario completo).

El historico de ventas se actualiza via `POST /sales-history/` (JSON) o
`POST /sales-history/upload` (CSV/XLSX/XML), solo administradores. El stock
fisico actual se actualiza via `POST /inventory/` (mismo patron de upsert). El
catalogo de precios/costos (`GET /products/`, `PATCH /products/{clasificador}`)
se siembra inicialmente con `make seed-catalog` a partir del precio historico
real promedio de cada categoria.

## Reportes PDF

`GET /reports/weekly?fecha_inicio=YYYY-MM-DD` y `GET /reports/monthly?fecha_inicio=...`
(solo administradores) generan y descargan un PDF con: demanda proyectada por
categoria (reutilizando `/predictions/range` internamente, sin logica de
inferencia duplicada), tabla de prioridades de reabastecimiento (Alta/Media/Baja
segun dias de inventario restante), 3 metricas de negocio por categoria (dias de
inventario restante, costo de oportunidad por quiebre de stock, costo aproximado
de reposicion), dos graficas (matplotlib, incrustadas en alta resolucion) y un
resumen ejecutivo generado por `gpt-4o-mini` (con fallback automatico por
plantilla si no hay `OPENAI_API_KEY` configurada o la llamada falla).

## Reentrenamiento (estructura lista, sin logica de entrenamiento aun)

`POST /retraining/trigger` (admin) registra una fila en `retraining_jobs`
(`status=pending`) y responde `202`, como gancho para un futuro worker/cola. La
tabla `sales_history` tiene columnas `ingested_at`/`updated_at` para que ese
futuro job pueda identificar que filas son nuevas desde el ultimo entrenamiento
(`metadata_modelo.json.fecha_entrenamiento`) sin ambiguedad.
