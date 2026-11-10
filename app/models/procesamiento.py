from datetime import datetime

from sqlalchemy import (
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Numeric,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Procesamiento(Base):
    __tablename__ = "procesamiento"
    __table_args__ = (
        # FK compuesta: la cámara debe pertenecer a la misma zona
        ForeignKeyConstraint(
            ["id_camara", "id_zona"],
            ["camara.id_camara", "camara.id_zona"],
            name="fk_proc_camara_zona",
        ),
    )

    id_procesamiento: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_zona: Mapped[int] = mapped_column(ForeignKey("zona.id_zona"), nullable=False)
    id_camara: Mapped[int | None] = mapped_column()
    id_usuario: Mapped[int | None] = mapped_column(ForeignKey("usuario.id_usuario"))
    tipo_fuente: Mapped[str] = mapped_column(
        Enum("imagen", "video", "stream", name="proc_tipo_fuente"), nullable=False
    )
    ruta_archivo: Mapped[str | None] = mapped_column(String(255))
    # EVENTO: cuándo se grabó / empezó el stream
    fecha_captura_inicio: Mapped[datetime] = mapped_column(nullable=False)
    # REGISTRO: cuándo lo procesó el sistema
    fecha_inicio_proceso: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    fecha_fin_proceso: Mapped[datetime | None] = mapped_column()
    estado: Mapped[str] = mapped_column(
        Enum("pendiente", "procesando", "completado", "error", name="proc_estado"),
        nullable=False,
        server_default="pendiente",
    )
    mensaje_error: Mapped[str | None] = mapped_column(Text)
    ultima_actividad: Mapped[datetime | None] = mapped_column()
    ultima_muestra: Mapped[datetime | None] = mapped_column()
    fps_procesamiento: Mapped[float | None] = mapped_column(Numeric(10, 3))
    retraso_seg: Mapped[float | None] = mapped_column(Numeric(12, 3))
    fecha_registro: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )