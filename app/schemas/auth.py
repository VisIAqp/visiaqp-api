from pydantic import BaseModel, ConfigDict, field_validator


class LoginRequest(BaseModel):
    username: str
    password: str

    @field_validator("password")
    @classmethod
    def password_max_72_bytes(cls, v: str) -> str:
        # bcrypt solo procesa los primeros 72 bytes
        if len(v.encode("utf-8")) > 72:
            raise ValueError("La contraseña no puede superar 72 bytes")
        return v


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UsuarioActual(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_usuario: int
    nombres: str
    apellidos: str
    username: str
    email: str
    estado: str