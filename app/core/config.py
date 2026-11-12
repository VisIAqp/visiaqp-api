"""
config.py
Configuración centralizada de la aplicación, leída desde variables de
entorno (.env). Usa pydantic-settings para validar tipos automáticamente.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    # Base de datos
    DATABASE_URL: str
    DATABASE_HOST: str | None = None
    DATABASE_PORT: int = 3306
    TEST_DATABASE_URL: str = ""

    # Autenticación
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Seguridad
    MOTOR_API_KEY: str = ""
    MOTOR_INACTIVIDAD_SEG: int = Field(default=120, ge=30, le=3600)
    CORS_ORIGINS: str = "http://localhost:4200"

    # Aplicación
    APP_NAME: str = "VisIAqp API"
    DEBUG: bool = False
    CONTEXTO_TIMEOUT_SEG: int = Field(default=8, ge=1, le=30)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def database_url(self) -> URL:
        url = make_url(self.DATABASE_URL)
        if self.DATABASE_HOST:
            return url.set(host=self.DATABASE_HOST, port=self.DATABASE_PORT)
        return url


# Instancia única, reutilizada en toda la app
settings = Settings()
