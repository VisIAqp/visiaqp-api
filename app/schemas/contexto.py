from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, computed_field, model_validator


class RangoClima(BaseModel):
    id_zona: int = Field(ge=1)
    desde: date
    hasta: date

    @model_validator(mode='after')
    def rango(self):
        if self.desde.year < 1940 or self.hasta < self.desde or (self.hasta - self.desde).days >= 31:
            raise ValueError('El rango debe incluir de 1 a 31 días, desde 1940')
        if self.hasta > datetime.now().date():
            raise ValueError('La sincronización de contexto no admite días futuros')
        return self


class EventoEntrada(BaseModel):
    fecha: date
    nombre: str = Field(min_length=1, max_length=150)
    tipo: Literal['feriado', 'no_laborable', 'evento']
    alcance: Literal['nacional', 'local']
    id_zona: int | None = Field(default=None, ge=1)
    referencia: HttpUrl = Field(max_length=500)
    activo: bool = True

    @model_validator(mode='after')
    def ambito(self):
        if self.referencia.username or self.referencia.password:
            raise ValueError('La referencia debe ser pública y no contener credenciales')
        self.nombre = self.nombre.strip()
        if not self.nombre:
            raise ValueError('El nombre no puede estar vacío')
        if self.alcance == 'local' and self.id_zona is None:
            raise ValueError('Un evento local requiere zona')
        if self.alcance == 'nacional' and self.id_zona is not None:
            raise ValueError('Un evento nacional no debe asignarse a una sola zona')
        return self


class EventoSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_evento: int
    fecha: date
    nombre: str
    tipo: str
    alcance: str
    id_zona: int | None
    fuente: str
    referencia: str
    activo: bool
    actualizado_en: datetime

    @computed_field
    @property
    def editable(self) -> bool:
        return self.fuente == 'manual'


class ClimaSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    hora: datetime
    temperatura_c: float | None
    precipitacion_mm: float | None
    humedad_porcentaje: float | None
    codigo_tiempo: int | None
    tipo_dato: str
    modelo: str
    fuente: str
    consultado_en: datetime


class SincronizacionSalida(BaseModel):
    estado: Literal['actualizado', 'cache']
    registros: int
    consultado_en: datetime


class EstadoSincronizacion(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ultimo_intento: datetime
    ultimo_exito: datetime | None
    estado: str
    detalle: str | None


from typing import Generic, TypeVar
from app.schemas.metricas import PuntoSerie, PaginaMetricas

T = TypeVar('T')


class PaginaContexto(BaseModel, Generic[T]):
    consultado_en: datetime
    zona_horaria: str = 'America/Lima'
    total: int
    limite: int
    desplazamiento: int
    tiene_mas: bool
    datos: list[T]
    sincronizacion: EstadoSincronizacion | None = None


class PaginaCalendario(PaginaContexto[EventoSalida]):
    aviso: str


class PaginaClima(PaginaContexto[ClimaSalida]):
    coordenadas_configuradas: bool
    atribucion: str


class PuntoContexto(PuntoSerie):
    temperatura_c: float | None
    precipitacion_mm: float | None
    humedad_porcentaje: float | None
    codigo_tiempo: int | None
    tipo_clima: str | None
    modelo_clima: str | None
    clima_consultado_en: datetime | None
    es_feriado: bool
    es_no_laborable: bool
    tiene_evento: bool


class PaginaSeriesContexto(PaginaMetricas[PuntoContexto]):
    aviso: str
