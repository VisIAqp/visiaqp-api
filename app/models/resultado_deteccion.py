from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ResultadoDeteccion(Base):
    __tablename__ = "resultado_deteccion"

    id_resultado: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_procesamiento: Mapped[int] = mapped_column(
        ForeignKey("procesamiento.id_procesamiento", ondelete="CASCADE"),
        nullable=False,
    )
    periodo_inicio: Mapped[datetime] = mapped_column(nullable=False)
    periodo_fin: Mapped[datetime] = mapped_column(nullable=False)
    cantidad_peatones: Mapped[int] = mapped_column(nullable=False)
    confianza_promedio: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    fecha_registro: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )