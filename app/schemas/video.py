from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VideoSync(BaseModel):
    nombre_archivo: str = Field(min_length=1, max_length=255)
    tamano_bytes: int = Field(ge=0)
    fecha_modificacion: datetime

    @field_validator("nombre_archivo")
    @classmethod
    def nombre_relativo_y_seguro(cls, v: str) -> str:
        # Defensa en profundidad: el motor ya valida, pero la API no confía
        if v.startswith("/") or "\\" in v or (len(v) > 1 and v[1] == ":"):
            raise ValueError("nombre_archivo debe ser una ruta relativa con '/'")
        if any(parte in ("", ".", "..") for parte in v.split("/")):
            raise ValueError("nombre_archivo contiene segmentos no permitidos")
        return v

    @field_validator("fecha_modificacion")
    @classmethod
    def sin_zona_horaria(cls, v: datetime) -> datetime:
        if v.tzinfo is not None:
            raise ValueError("Las fechas deben enviarse sin zona horaria")
        return v.replace(microsecond=0)


class SincronizarRequest(BaseModel):
    videos: list[VideoSync] = Field(max_length=10000)


class SincronizarResultado(BaseModel):
    registrados: int
    actualizados: int
    no_disponibles: int


class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_video: int
    nombre_archivo: str
    tamano_bytes: int
    fecha_modificacion: datetime
    disponible: bool
    fecha_ultima_sincronizacion: datetime