"""Precisión de las ventanas y trazabilidad de la configuración de captura."""
from alembic import op
import sqlalchemy as sa


revision = "9b1ad721df43"
down_revision = "f60d4b2359de"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("procesamiento", sa.Column("firma_captura", sa.String(64)))
    op.create_index("ix_proc_camara_firma_fuente", "procesamiento", ["id_camara", "firma_captura", "tipo_fuente"])
    op.execute("""
        ALTER TABLE resultado_deteccion
        MODIFY periodo_inicio DATETIME(6) NOT NULL,
        MODIFY periodo_fin DATETIME(6) NOT NULL,
        ADD COLUMN recibido_en DATETIME(6) NULL
    """)


def downgrade():
    # La aplicación anterior persiste con truncamiento al segundo.
    op.execute("""
        ALTER TABLE resultado_deteccion
        MODIFY periodo_inicio DATETIME NOT NULL,
        MODIFY periodo_fin DATETIME NOT NULL,
        DROP COLUMN recibido_en
    """)
    op.drop_index("ix_proc_camara_firma_fuente", table_name="procesamiento")
    op.drop_column("procesamiento", "firma_captura")
