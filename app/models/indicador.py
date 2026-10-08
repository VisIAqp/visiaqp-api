from datetime import datetime
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Indicador(Base):
    __tablename__ = "indicador"
    __table_args__ = (
        UniqueConstraint("id_zona", "periodo_tipo", "periodo_inicio", name="uq_indicador"),
    )

    id_indicador: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_zona: Mapped[int] = mapped_column(
        ForeignKey("zona.id_zona", ondelete="CASCADE"), nullable=False
    )
    periodo_tipo: Mapped[str] = mapped_column(
        Enum("hora", "dia", name="indicador_periodo_tipo"), nullable=False
    )
    periodo_inicio: Mapped[datetime] = mapped_column(nullable=False)
    periodo_fin: Mapped[datetime] = mapped_column(nullable=False)
    total_peatones: Mapped[int] = mapped_column(nullable=False, server_default="0")
    promedio_peatones: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, server_default="0"
    )
    max_peatones: Mapped[int] = mapped_column(nullable=False, server_default="0")
    nivel_concentracion: Mapped[str] = mapped_column(
        Enum("bajo", "medio", "alto", name="indicador_nivel"), nullable=False
    )
    fecha_calculo: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )