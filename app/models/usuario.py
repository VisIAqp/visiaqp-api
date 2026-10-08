from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Usuario(Base):
    __tablename__ = "usuario"

    id_usuario: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_rol: Mapped[int] = mapped_column(ForeignKey("rol.id_rol"), nullable=False)
    nombres: Mapped[str] = mapped_column(String(100), nullable=False)
    apellidos: Mapped[str] = mapped_column(String(100), nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    estado: Mapped[str] = mapped_column(
        Enum("activo", "inactivo", name="usuario_estado"),
        nullable=False,
        server_default="activo",
    )
    fecha_registro: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    rol: Mapped["Rol"] = relationship("Rol")