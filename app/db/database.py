from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Reemplaza 'root' y 'tu_password' con tus credenciales de MySQL Workbench
DATABASE_URL = "mysql+pymysql://root:1234@localhost:3306/visiaqp"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()