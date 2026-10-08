from datetime import datetime
from decimal import Decimal

from sqlalchemy import CHAR, Enum, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Zona(Base):
    __tablename__ = "zona"

    id_zona: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255))
    ubicacion: Mapped[str | None] = mapped_column(String(150))
    pais: Mapped[str] = mapped_column(CHAR(2), nullable=False, server_default="PE")
    latitud: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    longitud: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    estado: Mapped[str] = mapped_column(
        Enum("activa", "inactiva", name="zona_estado"),
        nullable=False,
        server_default="activa",
    )
    fecha_registro: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )