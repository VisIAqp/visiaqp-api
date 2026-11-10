"""Índice para consultas de métricas por rango de captura."""
from alembic import op

revision = "e59c3a1248cd"
down_revision = "d48b2f0137bc"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_resultado_periodo_proceso", "resultado_deteccion", ["periodo_inicio", "id_procesamiento"])


def downgrade():
    op.drop_index("ix_resultado_periodo_proceso", table_name="resultado_deteccion")
