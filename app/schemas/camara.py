from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CamaraMotor(BaseModel):
    """Respuesta SOLO para el motor de IA. Incluye url_stream (puede traer credenciales)."""

    model_config = ConfigDict(from_attributes=True)

    id_camara: int
    id_zona: int
    nombre: str
    url_stream: str
    zone_polygon: list[list[float]] | None = None
    estado: Literal["activa", "inactiva", "mantenimiento"]


def _validar_poligono(v: list[list[float]] | None):
    if v is None:
        return v
    if len(v) < 3:
        raise ValueError("El polígono necesita al menos 3 puntos")
    for punto in v:
        if len(punto) != 2 or not all(0 <= c <= 1 for c in punto):
            raise ValueError("Cada punto debe ser [x, y] con valores entre 0 y 1")
    return v


class CamaraCreate(BaseModel):
    id_zona: int
    nombre: str = Field(min_length=1, max_length=100)
    url_stream: str = Field(min_length=1, max_length=255)
    tipo: Literal["fija", "movil"] = "fija"
    estado: Literal["activa", "inactiva", "mantenimiento"] = "activa"
    intervalo_muestreo_seg: int = Field(default=60, gt=0)
    zone_polygon: list[list[float]] | None = None

    _poligono = field_validator("zone_polygon")(_validar_poligono)


class CamaraUpdate(BaseModel):
    id_zona: int | None = None
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    url_stream: str | None = Field(default=None, min_length=1, max_length=255)
    tipo: Literal["fija", "movil"] | None = None
    estado: Literal["activa", "inactiva", "mantenimiento"] | None = None
    intervalo_muestreo_seg: int | None = Field(default=None, gt=0)
    zone_polygon: list[list[float]] | None = None

    _poligono = field_validator("zone_polygon")(_validar_poligono)


class CamaraPublica(BaseModel):
    """Respuesta para el frontend. NUNCA incluye url_stream."""

    model_config = ConfigDict(from_attributes=True)

    id_camara: int
    id_zona: int
    nombre: str
    tipo: Literal["fija", "movil"]
    estado: Literal["activa", "inactiva", "mantenimiento"]
    intervalo_muestreo_seg: int
    zone_polygon: list[list[float]] | None = None
    ultima_conexion: datetime | None = None
    fecha_registro: datetime
    tiene_url_stream: bool = True