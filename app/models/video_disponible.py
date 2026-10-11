from datetime import datetime

from sqlalchemy import BigInteger, Boolean, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VideoDisponible(Base):
    __tablename__ = "video_disponible"
    __table_args__ = (UniqueConstraint("nombre_archivo", name="uq_video_nombre"),)

    id_video: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Ruta relativa a la carpeta del motor, con "/" como separador
    nombre_archivo: Mapped[str] = mapped_column(
        String(255, collation="utf8mb4_bin"), nullable=False
    )
    tamano_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fecha_modificacion: Mapped[datetime] = mapped_column(nullable=False)
    disponible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="1"
    )
    fecha_registro: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    fecha_ultima_sincronizacion: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )