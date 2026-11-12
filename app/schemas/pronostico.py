from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EstimacionOcupacion(BaseModel):
    horizonte_min: Literal[15, 30]
    objetivo_en: datetime
    promedio_presentes: float
    metodo: Literal["regresion_ridge", "persistencia"]


class PronosticoRespuesta(BaseModel):
    id_camara: int
    estado: Literal["disponible", "camara_no_apta", "sin_modelo", "sin_pronostico_vigente"]
    base_en: datetime | None = None
    emitido_en: datetime | None = None
    version_modelo: str | None = None
    estimaciones: list[EstimacionOcupacion] = Field(default_factory=list)
