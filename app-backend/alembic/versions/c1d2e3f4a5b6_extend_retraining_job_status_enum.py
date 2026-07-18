"""extend retraining_job_status enum

Revision ID: c1d2e3f4a5b6
Revises: 388f78f6f225
Create Date: 2026-07-18 21:15:00.000000

`retraining_jobs.status` es un ENUM nativo de Postgres (no un `String`), asi
que agregar valores nuevos requiere `ALTER TYPE ... ADD VALUE`, que Postgres
no permite dentro de la misma transaccion que otro DDL -- de ahi que esto
sea una migracion separada, cada `ALTER TYPE` en su propio bloque autocommit.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "388f78f6f225"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for valor in ("running", "success", "failed"):
        with op.get_context().autocommit_block():
            op.execute(f"ALTER TYPE retraining_job_status ADD VALUE IF NOT EXISTS '{valor}'")


def downgrade() -> None:
    raise NotImplementedError(
        "Postgres no permite DROP VALUE en un enum sin reconstruir el tipo "
        "completo (rename, crear nuevo, migrar columna, drop viejo). No "
        "implementado: proyecto pequeño, un solo entorno."
    )
