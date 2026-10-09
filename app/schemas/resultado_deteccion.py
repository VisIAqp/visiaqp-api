from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class ResultadoCreate(BaseModel):
    id_zona: int
    id_camara: int | None = None
    periodo_inicio: datetime
    periodo_fin: datetime
    cantidad_peatones: int = Field(ge=0)
    # El motor la envía en escala 0-1
    confianza_promedio: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validar_periodo(self):
        if self.periodo_fin < self.periodo_inicio:
            raise ValueError("periodo_fin no puede ser anterior a periodo_inicio")
        return self


class ResultadoCreado(BaseModel):
    id_resultado: int