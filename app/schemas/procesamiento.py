from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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