from typing import Literal

from pydantic import BaseModel, ConfigDict


class CamaraMotor(BaseModel):
    """Respuesta SOLO para el motor de IA. Incluye url_stream (puede traer credenciales)."""

    model_config = ConfigDict(from_attributes=True)

    id_camara: int
    id_zona: int
    nombre: str
    url_stream: str
    zone_polygon: list[list[float]] | None = None
    estado: Literal["activa", "inactiva", "mantenimiento"]