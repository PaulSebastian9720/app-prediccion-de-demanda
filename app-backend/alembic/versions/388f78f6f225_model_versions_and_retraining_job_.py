"""model versions and retraining job tracking

Revision ID: 388f78f6f225
Revises: b3c4d5e6f7a8
Create Date: 2026-07-18 21:06:02.762719

Agrega el versionado de modelo (`model_versions`) y el seguimiento real de
jobs de reentrenamiento (`retraining_jobs.started_at/completed_at/error_message
/model_version_id`). Tambien convierte `inventory_stock.stock_actual`/
`stock_minimo` de float a entero -- el stock fisico nunca es fraccionario --
redondeando los valores existentes en el mismo `ALTER COLUMN` (sin `UPDATE`
separado, atomico).
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '388f78f6f225'
down_revision: str | None = 'b3c4d5e6f7a8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('model_versions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('version_number', sa.Integer(), nullable=False),
    sa.Column('fecha_entrenamiento', sa.DateTime(timezone=True), nullable=False),
    sa.Column('artifacts_dir', sa.String(length=255), nullable=False),
    sa.Column('metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column('retraining_job_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['retraining_job_id'], ['retraining_jobs.id'], name=op.f('fk_model_versions_retraining_job_id_retraining_jobs'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_model_versions')),
    sa.UniqueConstraint('version_number', name=op.f('uq_model_versions_version_number'))
    )
    op.alter_column('model_versions', 'is_active', server_default=None)
    op.create_index(op.f('ix_model_versions_created_at'), 'model_versions', ['created_at'], unique=False)
    # Solo una version activa a la vez -- indice unico parcial, blinda contra
    # bugs/carreras ademas de la logica explicita de activacion en el codigo.
    op.create_index(
        'ux_model_versions_single_active', 'model_versions', ['is_active'],
        unique=True, postgresql_where=sa.text('is_active'),
    )

    # round(...)::integer en el propio ALTER COLUMN: corrige de una vez los
    # valores fraccionarios que ya existen (ej. 44.3 -> 44), sin paso extra.
    op.alter_column('inventory_stock', 'stock_actual',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               type_=sa.Integer(),
               postgresql_using='round(stock_actual)::integer',
               existing_nullable=False)
    op.alter_column('inventory_stock', 'stock_minimo',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               type_=sa.Integer(),
               postgresql_using='round(stock_minimo)::integer',
               existing_nullable=False)

    op.add_column('retraining_jobs', sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('retraining_jobs', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('retraining_jobs', sa.Column('error_message', sa.Text(), nullable=True))
    op.add_column('retraining_jobs', sa.Column('model_version_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(op.f('fk_retraining_jobs_model_version_id_model_versions'), 'retraining_jobs', 'model_versions', ['model_version_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint(op.f('fk_retraining_jobs_model_version_id_model_versions'), 'retraining_jobs', type_='foreignkey')
    op.drop_column('retraining_jobs', 'model_version_id')
    op.drop_column('retraining_jobs', 'error_message')
    op.drop_column('retraining_jobs', 'completed_at')
    op.drop_column('retraining_jobs', 'started_at')

    # int -> float es una conversion segura, no hace falta postgresql_using.
    op.alter_column('inventory_stock', 'stock_minimo',
               existing_type=sa.Integer(),
               type_=sa.DOUBLE_PRECISION(precision=53),
               existing_nullable=False)
    op.alter_column('inventory_stock', 'stock_actual',
               existing_type=sa.Integer(),
               type_=sa.DOUBLE_PRECISION(precision=53),
               existing_nullable=False)

    op.drop_index('ux_model_versions_single_active', table_name='model_versions')
    op.drop_index(op.f('ix_model_versions_created_at'), table_name='model_versions')
    op.drop_table('model_versions')
