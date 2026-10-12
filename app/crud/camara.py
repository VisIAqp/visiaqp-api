from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.camara import Camara
from app.schemas.camara import CamaraCreate, CamaraUpdate


def listar_activas(db: Session) -> list[Camara]:
    stmt = select(Camara).where(Camara.estado == "activa").order_by(Camara.id_camara)
    return list(db.scalars(stmt))


def obtener_en_zona(db: Session, id_camara: int, id_zona: int) -> Camara | None:
    """Devuelve la cámara solo si pertenece a esa zona."""
    stmt = select(Camara).where(
        Camara.id_camara == id_camara, Camara.id_zona == id_zona
    )
    return db.scalars(stmt).first()

def listar(db: Session, id_zona: int | None = None) -> list[Camara]:
    stmt = select(Camara).order_by(Camara.id_camara)
    if id_zona is not None:
        stmt = stmt.where(Camara.id_zona == id_zona)
    return list(db.scalars(stmt))


def obtener(db: Session, id_camara: int) -> Camara | None:
    return db.get(Camara, id_camara)


def crear(db: Session, datos: CamaraCreate) -> Camara:
    camara = Camara(**datos.model_dump())
    db.add(camara)
    db.commit()
    db.refresh(camara)
    return camara


def actualizar(db: Session, camara: Camara, datos: CamaraUpdate) -> Camara:
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(camara, campo, valor)
    db.commit()
    db.refresh(camara)
    return camara