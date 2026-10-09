from pydantic import BaseModel, ConfigDict


class RolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_rol: int
    nombre: str
    descripcion: str | None = None