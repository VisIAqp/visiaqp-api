"""Registra recálculos de indicadores pendientes."""

import sqlalchemy as sa
from alembic import op

revision = "3c1f421d8f40"
down_revision = "e287f0ad6841"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "recalculo_indicador",
        sa.Column("id_resultado", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("disponible_desde", sa.DateTime(), nullable=False),
        sa.Column("intentos", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(
            ["id_resultado"], ["resultado_deteccion.id_resultado"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id_resultado"),
    )
    op.create_index(
        "ix_recalculo_indicador_disponible", "recalculo_indicador",
        ["disponible_desde", "id_resultado"],
    )


def downgrade():
    op.drop_table("recalculo_indicador")
