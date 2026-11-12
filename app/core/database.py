"""
database.py
Configuración de SQLAlchemy: engine, sesión y clase base para los modelos.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

url = settings.database_url
connect_args = {"init_command": "SET time_zone = '-05:00'"} if url.get_driver_name() == "pymysql" else {}
engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    Dependency de FastAPI: entrega una sesión de BD por request y
    la cierra automáticamente al terminar, incluso si hay una excepción.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
