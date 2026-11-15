from datetime import datetime

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RecalculoIndicador(Base):
    __tablename__ = "recalculo_indicador"
    __table_args__ = (
        Index("ix_recalculo_indicador_disponible", "disponible_desde", "id_resultado"),
    )

    id_resultado: Mapped[int] = mapped_column(
        ForeignKey("resultado_deteccion.id_resultado", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
    )
    disponible_desde: Mapped[datetime] = mapped_column()
    intentos: Mapped[int] = mapped_column(server_default="0")
