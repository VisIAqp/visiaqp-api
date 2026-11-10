from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ResultadoDeteccion(Base):
    __tablename__ = "resultado_deteccion"
    __table_args__ = (Index("ix_resultado_periodo_proceso", "periodo_inicio", "id_procesamiento"), UniqueConstraint("id_procesamiento", "clave_ventana", name="uq_resultado_ventana"),)
    clave_ventana: Mapped[str | None] = mapped_column(String(36))

    id_resultado: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_procesamiento: Mapped[int] = mapped_column(
        ForeignKey("procesamiento.id_procesamiento", ondelete="CASCADE"),
        nullable=False,
    )
    periodo_inicio: Mapped[datetime] = mapped_column(nullable=False)
    periodo_fin: Mapped[datetime] = mapped_column(nullable=False)
    cantidad_peatones: Mapped[int] = mapped_column(nullable=False)
    confianza_promedio: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    promedio_presentes: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    max_presentes: Mapped[int | None] = mapped_column()
    segundos_observados: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    fecha_registro: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )