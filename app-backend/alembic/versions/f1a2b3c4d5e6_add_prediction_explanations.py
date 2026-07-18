"""add prediction_explanations table

Revision ID: f1a2b3c4d5e6
Revises: d4e5f6a7b8c9
Create Date: 2026-07-18 12:00:00.000000

Tabla 1:1 con `inference_logs` para la explicacion XAI de predicciones de un
solo dia (endpoint /predictions/day): resumen en lenguaje natural, factores
(perturbacion real, no conversion ingenua de SHAP), dia historico similar y
margen de error habitual del clasificador. Se deja fuera de `inference_logs`
porque `week`/`range`/`day_x` nunca la generan.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prediction_explanations",
        sa.Column("inference_log_id", sa.Uuid(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("prediccion", sa.Integer(), nullable=False),
        sa.Column("resumen", sa.String(length=2000), nullable=False),
        sa.Column("factores", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recomendacion", sa.String(length=500), nullable=True),
        sa.Column("dia_similar_fecha", sa.Date(), nullable=True),
        sa.Column("dia_similar_cantidad", sa.Integer(), nullable=True),
        sa.Column("margen_error_habitual", sa.Float(), nullable=True),
        sa.Column("generado_por", sa.String(length=16), nullable=False),
        sa.Column("modelo_llm", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["inference_log_id"],
            ["inference_logs.id"],
            name=op.f("fk_prediction_explanations_inference_log_id_inference_logs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("inference_log_id", name=op.f("pk_prediction_explanations")),
    )


def downgrade() -> None:
    op.drop_table("prediction_explanations")
