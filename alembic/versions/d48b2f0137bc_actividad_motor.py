"""Actividad del motor e identificación opcional de ventanas."""
from alembic import op
import sqlalchemy as sa

revision = "d48b2f0137bc"
down_revision = "c37a1e9026ab"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("procesamiento", sa.Column("ultima_actividad", sa.DateTime(), nullable=True))
    # Dar un plazo inicial a motores que estaban ejecutándose al actualizar.
    op.execute("UPDATE procesamiento SET ultima_actividad = NOW() WHERE estado = 'procesando'")
    op.add_column("procesamiento", sa.Column("ultima_muestra", sa.DateTime(), nullable=True))
    op.add_column("procesamiento", sa.Column("fps_procesamiento", sa.Numeric(10, 3), nullable=True))
    op.add_column("procesamiento", sa.Column("retraso_seg", sa.Numeric(12, 3), nullable=True))
    op.add_column("resultado_deteccion", sa.Column("clave_ventana", sa.String(36), nullable=True))
    op.create_unique_constraint("uq_resultado_ventana", "resultado_deteccion", ["id_procesamiento", "clave_ventana"])


def downgrade():
    op.drop_constraint("uq_resultado_ventana", "resultado_deteccion", type_="unique")
    op.drop_column("resultado_deteccion", "clave_ventana")
    for campo in ("retraso_seg", "fps_procesamiento", "ultima_muestra", "ultima_actividad"):
        op.drop_column("procesamiento", campo)
