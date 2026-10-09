from pydantic import BaseModel, ConfigDict, Field, model_validator


class UmbralIn(BaseModel):
    umbral_medio: int = Field(ge=0)
    umbral_alto: int = Field(ge=1)

    @model_validator(mode="after")
    def validar(self):
        if self.umbral_alto <= self.umbral_medio:
            raise ValueError("umbral_alto debe ser mayor que umbral_medio")
        return self


class UmbralOut(UmbralIn):
    model_config = ConfigDict(from_attributes=True)

    id_zona: int