"""Clima guardado, calendario y sincronización externa."""
from alembic import op
import sqlalchemy as sa

revision = "f60d4b2359de"
down_revision = "e59c3a1248cd"
branch_labels = None
depends_on = None


def upgrade():
    # Se congela la definición en esta revisión; no se usa create_all de la aplicación.
    op.create_table('clima_hora',
        sa.Column('id_clima',sa.Integer(),primary_key=True,autoincrement=True),
        sa.Column('id_zona',sa.Integer(),sa.ForeignKey('zona.id_zona'),nullable=False),
        sa.Column('hora',sa.DateTime(),nullable=False),
        sa.Column('latitud',sa.Numeric(10,7),nullable=False),sa.Column('longitud',sa.Numeric(10,7),nullable=False),
        sa.Column('latitud_modelo',sa.Numeric(10,7)),sa.Column('longitud_modelo',sa.Numeric(10,7)),
        sa.Column('temperatura_c',sa.Numeric(7,2)),sa.Column('precipitacion_mm',sa.Numeric(9,3)),
        sa.Column('humedad_porcentaje',sa.Numeric(6,2)),sa.Column('codigo_tiempo',sa.Integer()),
        sa.Column('tipo_dato',sa.String(30),nullable=False),sa.Column('modelo',sa.String(40),nullable=False),
        sa.Column('fuente',sa.String(30),nullable=False),sa.Column('consultado_en',sa.DateTime(),nullable=False),
        sa.UniqueConstraint('id_zona','hora','latitud','longitud','tipo_dato',name='uq_clima_zona_hora'))
    op.create_table('evento_calendario',
        sa.Column('id_evento',sa.Integer(),primary_key=True,autoincrement=True),
        sa.Column('clave_externa',sa.String(64),unique=True),sa.Column('fecha',sa.Date(),nullable=False),
        sa.Column('nombre',sa.String(150),nullable=False),sa.Column('tipo',sa.String(20),nullable=False),
        sa.Column('alcance',sa.String(20),nullable=False),sa.Column('id_zona',sa.Integer(),sa.ForeignKey('zona.id_zona')),
        sa.Column('fuente',sa.String(30),nullable=False),sa.Column('referencia',sa.String(500),nullable=False),
        sa.Column('activo',sa.Boolean(),nullable=False),sa.Column('actualizado_en',sa.DateTime(),nullable=False))
    op.create_index('ix_evento_calendario_fecha','evento_calendario',['fecha'])
    op.create_table('sincronizacion_contexto',
        sa.Column('clave',sa.String(160),primary_key=True),sa.Column('proveedor',sa.String(30),nullable=False),
        sa.Column('ultimo_intento',sa.DateTime(),nullable=False),sa.Column('ultimo_exito',sa.DateTime()),
        sa.Column('estado',sa.String(20),nullable=False),sa.Column('detalle',sa.String(250)))


def downgrade():
    op.drop_table('sincronizacion_contexto')
    op.drop_table('evento_calendario')
    op.drop_table('clima_hora')
