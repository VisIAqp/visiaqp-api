from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class IndicadorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_indicador: int
    id_zona: int
    periodo_tipo: Literal["hora", "dia"]
    periodo_inicio: datetime
    periodo_fin: datetime
    total_peatones: int
    promedio_peatones: float
    max_peatones: int
    nivel_concentracion: Literal["bajo", "medio", "alto"]


class IndicadorActual(IndicadorOut):
    nombre_zona: str


class RecalcularRequest(BaseModel):
    id_zona: int
    desde: datetime
    hasta: datetime

    @model_validator(mode="after")
    def validar_rango(self):
        if self.hasta <= self.desde:
            raise ValueError("hasta debe ser posterior a desde")
        if (self.hasta - self.desde).days > 31:
            raise ValueError("El rango máximo es de 31 días")
        return self


class RecalcularResultado(BaseModel):
    horas_recalculadas: int