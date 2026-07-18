"""Orquesta el reentrenamiento real del modelo y el versionado/activacion.

`run_retraining_job` corre como `BackgroundTasks` de FastAPI (ver
`app.api.v1.retraining.trigger_retraining`): abre su PROPIA sesion de BD via
`session_factory` (la de la request original ya se cerro para cuando esto
corre) y hace todo el trabajo pesado (`app.ml.training.train_new_model`)
envuelto en `asyncio.to_thread`, igual que el resto del codigo base.
"""

import asyncio
import logging
import time
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.constants import RetrainingJobStatus
from app.core.exceptions import NotFoundError
from app.db.models.model_version import ModelVersion
from app.db.models.retraining_job import RetrainingJob
from app.ml import training
from app.ml.registry import MLModelRegistry
from app.services import sales_history_service

logger = logging.getLogger("app.ml.retraining")


async def get_active_version(db: AsyncSession) -> ModelVersion | None:
    stmt = select(ModelVersion).where(ModelVersion.is_active.is_(True))
    return (await db.execute(stmt)).scalar_one_or_none()


async def has_active_job(db: AsyncSession) -> bool:
    """Si ya hay un job `pending`/`running`, no debe poder dispararse otro
    (evita reentrenar dos veces en paralelo sobre el mismo `artifacts/`)."""
    stmt = select(RetrainingJob.id).where(
        RetrainingJob.status.in_([RetrainingJobStatus.PENDING, RetrainingJobStatus.RUNNING])
    )
    return (await db.execute(stmt)).scalars().first() is not None


async def list_jobs(db: AsyncSession, *, page: int, page_size: int) -> tuple[list[RetrainingJob], int]:
    total = (await db.execute(select(func.count()).select_from(RetrainingJob))).scalar_one()
    stmt = (
        select(RetrainingJob)
        .order_by(RetrainingJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows), total


async def list_versions(db: AsyncSession) -> list[ModelVersion]:
    stmt = select(ModelVersion).order_by(ModelVersion.version_number.desc())
    return list((await db.execute(stmt)).scalars().all())


async def _next_version_number(db: AsyncSession) -> int:
    maximo = (await db.execute(select(func.max(ModelVersion.version_number)))).scalar_one()
    return (maximo or 0) + 1


def _version_folder_name(version_number: int, fecha_entrenamiento: str) -> str:
    """`v001__20260719T101530` -- el sufijo sale de `fecha_entrenamiento`
    (ISO, del metadata del entrenamiento) sin `:` para ser valido como nombre
    de carpeta."""
    compacta = fecha_entrenamiento.replace("-", "").replace(":", "")
    return f"v{version_number:03d}__{compacta}"


async def activate_version(
    db: AsyncSession, registry: MLModelRegistry, settings: Settings, version_id: UUID
) -> ModelVersion:
    """Activa `version_id`: apaga la version activa actual (si hay), prende la
    nueva, y recarga `registry` en caliente para que las predicciones futuras
    usen ese modelo de inmediato -- sin reiniciar el proceso. Misma logica que
    usa el camino automatico tras un reentrenamiento exitoso (ver
    `run_retraining_job`), factorizada aqui para no duplicarla."""
    version = await db.get(ModelVersion, version_id)
    if version is None:
        raise NotFoundError(f"No existe una version de modelo con id '{version_id}'.")

    actual = await get_active_version(db)
    if actual is not None and actual.id != version.id:
        actual.is_active = False
        # Flush ANTES de prender la nueva: el indice unico parcial
        # `ux_model_versions_single_active` exige que nunca haya dos filas
        # con is_active=true a la vez, y el orden de ejecucion de los
        # UPDATE dentro de un mismo flush no esta garantizado por fila de
        # insercion en Python -- sin este paso intermedio, Postgres puede
        # ver momentaneamente ambas filas en true y violar el indice.
        await db.flush()
    version.is_active = True
    await db.commit()

    await _reload_registry(registry, settings, version.artifacts_dir)
    return version


async def _reload_registry(registry: MLModelRegistry, settings: Settings, artifacts_dir: str) -> None:
    """`registry.reload` hace I/O de disco -- se corre en un hilo, nunca
    bloqueando el event loop (mismo criterio que la carga inicial)."""
    await asyncio.to_thread(registry.reload, settings.model_artifacts_dir / artifacts_dir)


async def run_retraining_job(
    job_id: UUID,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    registry: MLModelRegistry,
) -> None:
    """Ejecuta un job de reentrenamiento de punta a punta. Nunca deja que una
    excepcion se escape: cualquier fallo se refleja en `status=FAILED` +
    `error_message`, jamas tumba el proceso (esto corre en background, sin
    cliente esperando una respuesta HTTP a la que propagar el error)."""
    async with session_factory() as db:
        job = await db.get(RetrainingJob, job_id)
        if job is None:
            logger.error("run_retraining_job: job %s no encontrado, abortando.", job_id)
            return

        job.status = RetrainingJobStatus.RUNNING
        job.started_at = datetime.now()
        await db.commit()

        t0 = time.perf_counter()
        try:
            history = await sales_history_service.get_all_history(db)
            result = await asyncio.to_thread(training.train_new_model, history)

            version_number = await _next_version_number(db)
            fecha_entrenamiento = str(result.metadata["fecha_entrenamiento"])
            carpeta = _version_folder_name(version_number, fecha_entrenamiento)
            output_dir = settings.model_artifacts_dir / "models" / carpeta
            await asyncio.to_thread(training.save_training_result, result, output_dir)

            nueva_version = ModelVersion(
                version_number=version_number,
                fecha_entrenamiento=datetime.fromisoformat(fecha_entrenamiento),
                artifacts_dir=f"models/{carpeta}",
                metrics=result.metadata["metricas"],
                is_active=False,
                retraining_job_id=job.id,
            )
            db.add(nueva_version)
            await db.flush()

            activa = await get_active_version(db)
            mae_nuevo = result.metadata["metricas"]["prueba"]["MAE"]
            mejora = activa is None or mae_nuevo < activa.metrics["prueba"]["MAE"]
            if mejora:
                if activa is not None:
                    activa.is_active = False
                    # Igual que en `activate_version`: flush antes de prender
                    # la nueva para no violar el indice unico parcial
                    # `ux_model_versions_single_active` (el orden de los
                    # UPDATE dentro de un flush no sigue el orden de
                    # asignacion en Python).
                    await db.flush()
                nueva_version.is_active = True

            job.model_version_id = nueva_version.id
            job.status = RetrainingJobStatus.SUCCESS
            job.completed_at = datetime.now()
            await db.commit()

            if mejora:
                await _reload_registry(registry, settings, nueva_version.artifacts_dir)

            logger.info(
                "Reentrenamiento %s completado en %.1fs -> version v%03d (MAE prueba=%.3f, %s)",
                job.id,
                time.perf_counter() - t0,
                version_number,
                mae_nuevo,
                "activada" if mejora else "guardada sin activar",
            )
        except Exception as exc:
            await db.rollback()
            job.status = RetrainingJobStatus.FAILED
            job.error_message = str(exc)
            job.completed_at = datetime.now()
            await db.commit()
            logger.warning("Reentrenamiento %s fallo: %s", job.id, exc, exc_info=True)
