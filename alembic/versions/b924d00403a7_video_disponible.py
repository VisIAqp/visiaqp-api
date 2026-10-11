"""video_disponible

Revision ID: b924d00403a7
Revises: 6e1bd5292f4e
Create Date: 2026-10-10 17:27:56.550319

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b924d00403a7'
down_revision: Union[str, Sequence[str], None] = '6e1bd5292f4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "video_disponible",
        sa.Column("id_video", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nombre_archivo", sa.String(255, collation="utf8mb4_bin"), nullable=False),
        sa.Column("tamano_bytes", sa.BigInteger(), nullable=False),
        sa.Column("fecha_modificacion", sa.DateTime(), nullable=False),
        sa.Column("disponible", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("fecha_registro", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "fecha_ultima_sincronizacion",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id_video"),
        sa.UniqueConstraint("nombre_archivo", name="uq_video_nombre"),
        sa.CheckConstraint("tamano_bytes >= 0", name="ck_video_tamano"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("idx_video_disponible", "video_disponible", ["disponible"])


def downgrade() -> None:
    op.drop_index("idx_video_disponible", table_name="video_disponible")
    op.drop_table("video_disponible")
