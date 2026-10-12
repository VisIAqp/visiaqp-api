from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ZonaBase(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    descripcion: str | None = Field(default=None, max_length=255)
    ubicacion: str | None = Field(default=None, max_length=150)
    pais: str = Field(default="PE", pattern=r"^[A-Z]{2}$")
    latitud: Decimal | None = Field(default=None, ge=-90, le=90)
    longitud: Decimal | None = Field(default=None, ge=-180, le=180)


class ZonaCreate(ZonaBase):
    pass


class ZonaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    descripcion: str | None = Field(default=None, max_length=255)
    ubicacion: str | None = Field(default=None, max_length=150)
    pais: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    latitud: Decimal | None = Field(default=None, ge=-90, le=90)
    longitud: Decimal | None = Field(default=None, ge=-180, le=180)
    estado: Literal["activa", "inactiva"] | None = None


class ZonaOut(ZonaBase):
    model_config = ConfigDict(from_attributes=True)

    id_zona: int
    estado: Literal["activa", "inactiva"]
    fecha_registro: datetime