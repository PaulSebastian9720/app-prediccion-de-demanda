"""Tests de integracion del reentrenamiento real y el versionado de modelo.

Nota sobre `BackgroundTasks`: con `httpx.AsyncClient`/`ASGITransport`, las
tareas programadas con `BackgroundTasks.add_task` corren DENTRO del mismo
`await client.post(...)` (Starlette las ejecuta antes de devolver el control),
asi que estos tests pueden verificar el estado final del job sin hacer
polling real -- a diferencia de un despliegue real, donde `POST /trigger`
responde antes de que el entrenamiento termine.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.constants import RetrainingJobStatus
from app.db.models.model_version import ModelVersion
from app.db.models.retraining_job import RetrainingJob
from app.ml.registry import MLModelRegistry


@pytest.fixture(autouse=True)
def _use_tmp_artifacts_dir(app: FastAPI, tmp_path: Path) -> None:
    """Estos tests SI entrenan y guardan archivos de modelo reales (no
    mockeados) -- deben caer en un directorio temporal de pytest, nunca en
    el `artifacts/` real del repo, donde vive el modelo de referencia que
    otros tests (`test_features.py`, `test_prediction_endpoints.py`)
    comparan por valor EXACTO. Sin esto, cada corrida ensuciaria el repo con
    carpetas `models/v001__...` reales y ademas rompería esos otros tests."""
    original_settings = app.state.settings
    app.state.settings = original_settings.model_copy(update={"model_artifacts_dir": tmp_path})


@pytest.fixture(autouse=True)
async def _restore_shared_registry(ml_registry: MLModelRegistry) -> AsyncIterator[None]:
    """`ml_registry` es una fixture de sesion (un solo modelo cargado para
    toda la corrida de tests, por rendimiento) -- pero `activate_version`
    hace un `reload()` real sobre ESA misma instancia compartida. Sin
    restaurarla, un test de aqui dejaria cargado un modelo recien
    reentrenado (con pesos distintos al de referencia) para el resto de la
    sesion, rompiendo las aserciones de valor exacto de otros tests
    (`test_features.py`, `test_prediction_endpoints.py`, etc)."""
    original_dir = ml_registry.artifacts_dir
    yield
    if ml_registry.artifacts_dir != original_dir:
        ml_registry.reload(original_dir)


async def test_trigger_requires_admin(client: AsyncClient, user_headers: dict[str, str]) -> None:
    r = await client.post("/retraining/trigger", headers=user_headers)
    assert r.status_code == 403


async def test_trigger_trains_and_activates_first_version(
    client: AsyncClient, admin_headers: dict[str, str], seeded_sales_history: None
) -> None:
    r = await client.post("/retraining/trigger", headers=admin_headers)
    assert r.status_code == 202
    job_id = r.json()["id"]

    job = (await client.get(f"/retraining/jobs/{job_id}", headers=admin_headers)).json()
    assert job["status"] == "success", job.get("error_message")
    assert job["model_version_id"] is not None

    versions = (await client.get("/retraining/versions", headers=admin_headers)).json()
    assert len(versions) == 1
    # Sin ninguna version activa previa, la primera siempre se activa.
    assert versions[0]["is_active"] is True
    assert versions[0]["version_number"] == 1
    assert "MAE" in versions[0]["metrics"]["prueba"]


async def test_trigger_rejects_while_a_job_is_pending(
    client: AsyncClient, admin_headers: dict[str, str], db_session_factory: async_sessionmaker
) -> None:
    # Con `ASGITransport`, `BackgroundTasks` corre dentro del mismo `await
    # client.post(...)` (ver nota del modulo): un trigger normal siempre
    # termina en success/failed antes de responder, nunca queda "pendiente"
    # de verdad para el siguiente request. Para probar el 409 hace falta
    # insertar un job `pending` directo, sin pasar por el endpoint (simula el
    # caso real: dos usuarios disparando casi al mismo tiempo).
    async with db_session_factory() as db:
        db.add(RetrainingJob(status=RetrainingJobStatus.PENDING))
        await db.commit()

    r = await client.post("/retraining/trigger", headers=admin_headers)
    assert r.status_code == 409


async def test_get_unknown_job_returns_404(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await client.get(
        "/retraining/jobs/00000000-0000-0000-0000-000000000000", headers=admin_headers
    )
    assert r.status_code == 404


async def test_list_jobs_paginated(
    client: AsyncClient, admin_headers: dict[str, str], seeded_sales_history: None
) -> None:
    await client.post("/retraining/trigger", headers=admin_headers)

    r = await client.get("/retraining/jobs", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["total_items"] >= 1
    assert body["items"][0]["status"] in ("success", "failed")


async def test_activate_version_manually(
    client: AsyncClient, admin_headers: dict[str, str], seeded_sales_history: None
) -> None:
    await client.post("/retraining/trigger", headers=admin_headers)
    versions = (await client.get("/retraining/versions", headers=admin_headers)).json()
    version_id = versions[0]["id"]

    r = await client.post(f"/retraining/versions/{version_id}/activate", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["is_active"] is True

    # La prediccion refleja el modelo activado (recarga en caliente, sin
    # reiniciar el proceso).
    pred = await client.post(
        "/predictions/day",
        json={"clasificador": "PASEO_SUJECION", "fecha": "2026-07-02"},
        headers=admin_headers,
    )
    assert pred.status_code == 200


async def test_activate_switches_between_two_different_versions(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session_factory: async_sessionmaker,
    seeded_sales_history: None,
) -> None:
    """Regresion: activar una version DISTINTA a la que ya esta activa debe
    apagar la vieja y prender la nueva sin violar el indice unico parcial
    `ux_model_versions_single_active` (bug real encontrado probando en vivo:
    el orden de los `UPDATE` dentro de un mismo flush de SQLAlchemy no sigue
    el orden de asignacion en Python, asi que Postgres podia ver
    momentaneamente dos filas con `is_active=true`).

    Dispara un reentrenamiento real (para tener archivos de modelo de verdad
    en disco) y despues inserta una segunda fila `model_versions` que
    reutiliza esos MISMOS archivos (`artifacts_dir` igual) -- asi se prueba
    la logica de swap/activacion sin pagar el costo de una segunda
    corrida real de entrenamiento."""
    trigger = (await client.post("/retraining/trigger", headers=admin_headers)).json()
    job = (await client.get(f"/retraining/jobs/{trigger['id']}", headers=admin_headers)).json()
    assert job["status"] == "success", job.get("error_message")

    v1 = (await client.get("/retraining/versions", headers=admin_headers)).json()[0]
    assert v1["is_active"] is True

    async with db_session_factory() as db:
        row_v1 = await db.get(ModelVersion, uuid.UUID(v1["id"]))
        assert row_v1 is not None
        v2 = ModelVersion(
            version_number=2,
            fecha_entrenamiento=datetime(2026, 1, 2),
            artifacts_dir=row_v1.artifacts_dir,
            metrics=row_v1.metrics,
            is_active=False,
        )
        db.add(v2)
        await db.commit()
        v2_id = v2.id

    r = await client.post(f"/retraining/versions/{v2_id}/activate", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is True

    versions = {
        v["version_number"]: v["is_active"]
        for v in (await client.get("/retraining/versions", headers=admin_headers)).json()
    }
    assert versions == {1: False, 2: True}


async def test_activate_unknown_version_returns_404(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await client.post(
        "/retraining/versions/00000000-0000-0000-0000-000000000000/activate",
        headers=admin_headers,
    )
    assert r.status_code == 404
