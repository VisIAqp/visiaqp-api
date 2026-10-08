from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UmbralConcentracion(Base):
    __tablename__ = "umbral_concentracion"

    id_umbral: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_zona: Mapped[int] = mapped_column(
        ForeignKey("zona.id_zona", ondelete="CASCADE"), unique=True, nullable=False
    )
    umbral_medio: Mapped[int] = mapped_column(nullable=False)
    umbral_alto: Mapped[int] = mapped_column(nullable=False)