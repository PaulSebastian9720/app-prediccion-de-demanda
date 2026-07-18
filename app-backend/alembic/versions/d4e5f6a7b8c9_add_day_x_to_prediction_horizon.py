"""add day_x to prediction_horizon enum

Revision ID: d4e5f6a7b8c9
Revises: 20b7de432cbd
Create Date: 2026-07-16 17:05:00.000000

El enum `prediction_horizon` se creo en la migracion inicial solo con
'day'/'week'/'range', pero el codigo (`PredictionHorizon.DAY_X`) tambien emite
'day_x' al registrar las predicciones del endpoint /predictions/day-x. Sin ese
valor, el INSERT en `inference_logs` de esas predicciones falla en Postgres
(`invalid input value for enum prediction_horizon: "day_x"`); el error se captura
y se degrada a un warning, pero el log de auditoria de la prediccion se pierde.
Aqui se agrega el valor faltante para dejar la BD alineada con el modelo.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "20b7de432cbd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostgreSQL 12+ permite ALTER TYPE ... ADD VALUE dentro de una transaccion
    # siempre que el nuevo valor no se USE en la misma transaccion (aqui solo se
    # agrega). IF NOT EXISTS hace la migracion idempotente/re-ejecutable.
    op.execute("ALTER TYPE prediction_horizon ADD VALUE IF NOT EXISTS 'day_x'")


def downgrade() -> None:
    # PostgreSQL no soporta eliminar un valor de un enum sin recrear el tipo
    # completo (migrando la columna a un enum nuevo). Como 'day_x' es un valor
    # valido del dominio, el downgrade se deja como un no-op deliberado.
    pass
