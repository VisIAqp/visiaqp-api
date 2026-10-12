import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict, field_validator

_CREDENCIALES = re.compile(r"(\w+://)[^/\s@]+@")


class ProcesamientoCreate(BaseModel):
    id_zona: int
    id_camara: int | None = None
    tipo_fuente: Literal["imagen", "video", "stream"]
    ruta_archivo: str | None = Field(default=None, max_length=255)
    fecha_captura_inicio: datetime


class ProcesamientoCreado(BaseModel):
    id_procesamiento: int


class ProcesamientoCierre(BaseModel):
    estado: Literal["completado", "error"]
    fecha_fin_proceso: datetime | None = None
    mensaje_error: str | None = None


class ProcesamientoCerrado(BaseModel):
    id_procesamiento: int
    estado: str


class SolicitudCreate(BaseModel):
    id_video: int
    id_camara: int
    fecha_captura_inicio: datetime

    @field_validator("fecha_captura_inicio")
    @classmethod
    def sin_zona_horaria(cls, v: datetime) -> datetime:
        if v.tzinfo is not None:
            raise ValueError("Las fechas deben enviarse sin zona horaria")
        return v.replace(microsecond=0)


class PendienteMotor(BaseModel):
    """Para el motor. No incluye url_stream."""

    id_procesamiento: int
    id_zona: int
    id_camara: int
    nombre_camara: str
    nombre_archivo: str
    fecha_captura_inicio: datetime
    zone_polygon: list[list[float]] | None = None


class ProcesamientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_procesamiento: int
    id_zona: int
    id_camara: int | None
    id_usuario: int | None
    tipo_fuente: Literal["imagen", "video", "stream"]
    ruta_archivo: str | None
    fecha_captura_inicio: datetime
    fecha_inicio_proceso: datetime
    fecha_fin_proceso: datetime | None
    estado: Literal["pendiente", "procesando", "completado", "error"]
    mensaje_error: str | None
    fecha_registro: datetime

    @field_validator("mensaje_error")
    @classmethod
    def ocultar_credenciales(cls, v: str | None) -> str | None:
        # El motor puede incluir una URL con usuario:clave en sus errores
        return _CREDENCIALES.sub(r"\1***@", v) if v else v