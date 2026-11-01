"""Contexto guardado: clima modelado, calendario y control de sincronización."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ClimaHora(Base):
    __tablename__ = 'clima_hora'
    __table_args__ = (UniqueConstraint('id_zona', 'hora', 'latitud', 'longitud', 'tipo_dato', name='uq_clima_zona_hora'),)
    id_clima: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_zona: Mapped[int] = mapped_column(ForeignKey('zona.id_zona'), nullable=False)
    hora: Mapped[datetime] = mapped_column(nullable=False)
    latitud: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    longitud: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    latitud_modelo: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    longitud_modelo: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    temperatura_c: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    precipitacion_mm: Mapped[Decimal | None] = mapped_column(Numeric(9, 3))
    humedad_porcentaje: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    codigo_tiempo: Mapped[int | None] = mapped_column()
    tipo_dato: Mapped[str] = mapped_column(String(30))
    modelo: Mapped[str] = mapped_column(String(40))
    fuente: Mapped[str] = mapped_column(String(30), default='open_meteo')
    consultado_en: Mapped[datetime] = mapped_column(default=datetime.now)


class EventoCalendario(Base):
    __tablename__ = 'evento_calendario'
    id_evento: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    clave_externa: Mapped[str | None] = mapped_column(String(64), unique=True)
    fecha: Mapped[date] = mapped_column(nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(150))
    tipo: Mapped[str] = mapped_column(String(20))
    alcance: Mapped[str] = mapped_column(String(20))
    id_zona: Mapped[int | None] = mapped_column(ForeignKey('zona.id_zona'))
    fuente: Mapped[str] = mapped_column(String(30), default='manual')
    referencia: Mapped[str] = mapped_column(String(500))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    actualizado_en: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)


class SincronizacionContexto(Base):
    __tablename__ = 'sincronizacion_contexto'
    clave: Mapped[str] = mapped_column(String(160), primary_key=True)
    proveedor: Mapped[str] = mapped_column(String(30))
    ultimo_intento: Mapped[datetime] = mapped_column(nullable=False)
    ultimo_exito: Mapped[datetime | None] = mapped_column()
    estado: Mapped[str] = mapped_column(String(20))
    detalle: Mapped[str | None] = mapped_column(String(250))
