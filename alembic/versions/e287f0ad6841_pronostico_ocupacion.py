"""Modelo y pronóstico vigente de ocupación por cámara."""
from alembic import op
import sqlalchemy as sa


revision = "e287f0ad6841"
down_revision = "9b1ad721df43"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "modelo_ocupacion",
        sa.Column("id_camara", sa.Integer(), sa.ForeignKey("camara.id_camara", ondelete="CASCADE"), primary_key=True),
        sa.Column("firma_captura", sa.String(64), nullable=False),
        sa.Column("version", sa.String(36), nullable=False),
        sa.Column("hasta_datos", sa.DateTime(), nullable=False),
        sa.Column("artefacto", sa.JSON(), nullable=False),
    )
    op.create_table(
        "pronostico_ocupacion",
        sa.Column("id_camara", sa.Integer(), sa.ForeignKey("camara.id_camara", ondelete="CASCADE"), primary_key=True),
        sa.Column("version_modelo", sa.String(36), nullable=False),
        sa.Column("base_en", sa.DateTime(), nullable=False),
        sa.Column("emitido_en", sa.DateTime(), nullable=False),
        sa.Column("estimaciones", sa.JSON(), nullable=False),
    )


def downgrade():
    op.drop_table("pronostico_ocupacion")
    op.drop_table("modelo_ocupacion")
