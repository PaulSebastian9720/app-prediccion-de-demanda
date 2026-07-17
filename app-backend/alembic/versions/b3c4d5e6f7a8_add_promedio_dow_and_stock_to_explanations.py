"""add promedio_dia_semana and stock_actual to prediction_explanations

Revision ID: b3c4d5e6f7a8
Revises: a7b8c9d0e1f2
Create Date: 2026-07-19 20:30:00.000000

Dos datos mas para ayudar a explicar el "por que" de una prediccion sin
tecnicismos: el promedio historico de ese mismo dia de la semana (solo
aplica a /day y /day-x) y el stock fisico actual de la categoria al momento
de generar la explicacion (para comparar contra la demanda predicha).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "prediction_explanations", sa.Column("promedio_dia_semana", sa.Float(), nullable=True)
    )
    op.add_column("prediction_explanations", sa.Column("stock_actual", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("prediction_explanations", "stock_actual")
    op.drop_column("prediction_explanations", "promedio_dia_semana")
