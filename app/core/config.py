"""
config.py
Configuración centralizada de la aplicación, leída desde variables de
entorno (.env). Usa pydantic-settings para validar tipos automáticamente.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Base de datos
    DATABASE_URL: str

    # Autenticación
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Aplicación
    APP_NAME: str = "VisIAqp API"
    DEBUG: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


# Instancia única, reutilizada en toda la app
settings = Settings()