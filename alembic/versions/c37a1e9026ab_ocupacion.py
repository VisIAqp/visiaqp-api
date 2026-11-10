"""Ocupación opcional sin reinterpretar los conteos históricos."""
from alembic import op
import sqlalchemy as sa

revision = "c37a1e9026ab"
down_revision = "b924d00403a7"
branch_labels = None
depends_on = None


def upgrade():
    for tabla in ("resultado_deteccion", "indicador"):
        op.add_column(tabla, sa.Column("promedio_presentes", sa.Numeric(12, 4), nullable=True))
        op.add_column(tabla, sa.Column("max_presentes", sa.Integer(), nullable=True))
        op.add_column(tabla, sa.Column("segundos_observados", sa.Numeric(14, 4), nullable=True))
    op.add_column("indicador", sa.Column("nivel_ocupacion", sa.String(10), nullable=True))
    op.add_column("indicador", sa.Column("estado_ocupacion", sa.String(40), nullable=False, server_default="sin_datos"))


def downgrade():
    op.drop_column("indicador", "estado_ocupacion")
    op.drop_column("indicador", "nivel_ocupacion")
    for tabla in ("resultado_deteccion", "indicador"):
        for campo in ("segundos_observados", "max_presentes", "promedio_presentes"):
            op.drop_column(tabla, campo)
