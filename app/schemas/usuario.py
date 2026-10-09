from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _validar_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres")
    if len(v.encode("utf-8")) > 72:
        raise ValueError("La contraseña no puede superar 72 bytes")
    return v


class UsuarioCreate(BaseModel):
    id_rol: int
    nombres: str = Field(min_length=1, max_length=100)
    apellidos: str = Field(min_length=1, max_length=100)
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str

    _pwd = field_validator("password")(_validar_password)


class UsuarioUpdate(BaseModel):
    id_rol: int | None = None
    nombres: str | None = Field(default=None, min_length=1, max_length=100)
    apellidos: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    estado: Literal["activo", "inactivo"] | None = None


class CambiarPassword(BaseModel):
    password_nueva: str

    _pwd = field_validator("password_nueva")(_validar_password)


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_usuario: int
    id_rol: int
    nombres: str
    apellidos: str
    username: str
    email: str
    estado: Literal["activo", "inactivo"]
    fecha_registro: datetime