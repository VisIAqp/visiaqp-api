"""
config.py
Configuración centralizada de la aplicación, leída desde variables de
entorno (.env). Usa pydantic-settings para validar tipos automáticamente.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # Base de datos
    DATABASE_URL: str
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


# Instancia única, reutilizada en toda la app
settings = Settings()