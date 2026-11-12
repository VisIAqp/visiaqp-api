from datetime import datetime

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ModeloOcupacion(Base):
    __tablename__ = "modelo_ocupacion"

    id_camara: Mapped[int] = mapped_column(ForeignKey("camara.id_camara", ondelete="CASCADE"), primary_key=True)
    firma_captura: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(36))
    hasta_datos: Mapped[datetime] = mapped_column()
    artefacto: Mapped[dict] = mapped_column(JSON)


class PronosticoOcupacion(Base):
    __tablename__ = "pronostico_ocupacion"

    id_camara: Mapped[int] = mapped_column(ForeignKey("camara.id_camara", ondelete="CASCADE"), primary_key=True)
    version_modelo: Mapped[str] = mapped_column(String(36))
    base_en: Mapped[datetime] = mapped_column()
    emitido_en: Mapped[datetime] = mapped_column()
    estimaciones: Mapped[list] = mapped_column(JSON)
