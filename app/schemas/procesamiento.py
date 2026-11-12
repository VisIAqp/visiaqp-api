import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.core.config import settings
from app.core.tiempo import hora_lima

_CREDENCIALES = re.compile(r"(\w+://)[^/\s@]+@")


class ProcesamientoCreate(BaseModel):
    id_zona: int
    id_camara: int | None = None
    tipo_fuente: Literal["imagen", "video", "stream"]
    ruta_archivo: str | None = Field(default=None, max_length=255)
    fecha_captura_inicio: datetime
    firma_captura: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    _fecha_lima = field_validator("fecha_captura_inicio")(hora_lima)


class ProcesamientoCreado(BaseModel):
    id_procesamiento: int


class ProcesamientoCierre(BaseModel):
    estado: Literal["completado", "error"]
    fecha_fin_proceso: datetime | None = None
    mensaje_error: str | None = None

    @field_validator("fecha_fin_proceso")
    @classmethod
    def fecha_lima(cls, valor: datetime | None) -> datetime | None:
        return hora_lima(valor) if valor is not None else None


class ActividadMotor(BaseModel):
    ultima_muestra: datetime | None = None
    fps_procesamiento: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    # Edad desde la recepción local, no latencia desde el sensor de la cámara.
    retraso_seg: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @field_validator("ultima_muestra")
    @classmethod
    def fecha_lima(cls, valor: datetime | None) -> datetime | None:
        return hora_lima(valor) if valor is not None else None


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
    intervalo_muestreo_seg: int = 60


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
    inactividad_limite_seg: int = Field(default_factory=lambda: settings.MOTOR_INACTIVIDAD_SEG)
    ultima_actividad: datetime | None = None
    ultima_muestra: datetime | None = None
    fps_procesamiento: float | None = None
    retraso_seg: float | None = None

    @field_validator("mensaje_error")
    @classmethod
    def ocultar_credenciales(cls, v: str | None) -> str | None:
        # El motor puede incluir una URL con usuario:clave en sus errores
        return _CREDENCIALES.sub(r"\1***@", v) if v else v
