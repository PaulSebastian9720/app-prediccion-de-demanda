"""add historial_reciente to prediction_explanations

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-07-19 00:30:00.000000

Agrega `historial_reciente` (ultimos ~14 dias de historial real antes del dia
explicado) para que el frontend pueda dibujar un grafico de tendencia junto
al texto de la explicacion, en vez de solo mostrar la redaccion en prosa.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "prediction_explanations",
        sa.Column(
            "historial_reciente",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )
    # El server_default solo hace falta para rellenar filas existentes; las
    # nuevas filas siempre lo mandan explicito desde la aplicacion.
    op.alter_column("prediction_explanations", "historial_reciente", server_default=None)


def downgrade() -> None:
    op.drop_column("prediction_explanations", "historial_reciente")
