from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.tiempo import hora_lima


class ResultadoCreate(BaseModel):
    clave_ventana: str | None = Field(default=None, min_length=1, max_length=36)
    id_zona: int
    id_camara: int | None = None
    periodo_inicio: datetime
    periodo_fin: datetime
    cantidad_peatones: int = Field(ge=0)
    # El motor la envía en escala 0-1
    confianza_promedio: float | None = Field(default=None, ge=0, le=1)

    # Campos opcionales: motores antiguos siguen enviando el contrato original.
    promedio_presentes: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    max_presentes: int | None = Field(default=None, ge=0)
    segundos_observados: float | None = Field(default=None, ge=0.00005, allow_inf_nan=False)

    _fechas_lima = field_validator("periodo_inicio", "periodo_fin")(hora_lima)

    @model_validator(mode="after")
    def validar_periodo(self):
        if self.periodo_fin < self.periodo_inicio:
            raise ValueError("periodo_fin no puede ser anterior a periodo_inicio")
        ocupacion = (self.promedio_presentes, self.max_presentes, self.segundos_observados)
        if any(v is not None for v in ocupacion):
            if any(v is None for v in ocupacion):
                raise ValueError("La ocupación requiere promedio, máximo y segundos observados")
            if self.promedio_presentes > self.max_presentes or self.max_presentes > self.cantidad_peatones:
                raise ValueError("Se requiere promedio <= máximo <= identificadores por ventana")
            duracion = (self.periodo_fin - self.periodo_inicio).total_seconds()
            if duracion <= 0 or self.segundos_observados > duracion + 0.001:
                raise ValueError("Los segundos observados no pueden superar la duración de la ventana")
        return self


class ResultadoCreado(BaseModel):
    id_resultado: int
