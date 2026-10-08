from datetime import datetime

from sqlalchemy import JSON, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Camara(Base):
    __tablename__ = "camara"
    __table_args__ = (
        # Requerida por la FK compuesta de procesamiento
        UniqueConstraint("id_camara", "id_zona", name="uq_camara_id_zona"),
    )

    id_camara: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_zona: Mapped[int] = mapped_column(ForeignKey("zona.id_zona"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    # OJO: puede contener credenciales. Nunca exponerlo al frontend.
    url_stream: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo: Mapped[str] = mapped_column(
        Enum("fija", "movil", name="camara_tipo"),
        nullable=False,
        server_default="fija",
    )
    estado: Mapped[str] = mapped_column(
        Enum("activa", "inactiva", "mantenimiento", name="camara_estado"),
        nullable=False,
        server_default="activa",
    )
    intervalo_muestreo_seg: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="60"
    )
    zone_polygon: Mapped[list | None] = mapped_column(JSON)
    ultima_conexion: Mapped[datetime | None] = mapped_column()
    fecha_registro: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    zona: Mapped["Zona"] = relationship("Zona")