from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.zona import Zona
from app.schemas.zona import ZonaCreate, ZonaUpdate


def listar(db: Session, solo_activas: bool = False) -> list[Zona]:
    stmt = select(Zona).order_by(Zona.nombre)
    if solo_activas:
        stmt = stmt.where(Zona.estado == "activa")
    return list(db.scalars(stmt))


def obtener(db: Session, id_zona: int) -> Zona | None:
    return db.get(Zona, id_zona)


def obtener_por_nombre(db: Session, nombre: str) -> Zona | None:
    return db.scalars(select(Zona).where(Zona.nombre == nombre)).first()


def crear(db: Session, datos: ZonaCreate) -> Zona:
    zona = Zona(**datos.model_dump())
    db.add(zona)
    db.commit()
    db.refresh(zona)
    return zona


def actualizar(db: Session, zona: Zona, datos: ZonaUpdate) -> Zona:
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(zona, campo, valor)
    db.commit()
    db.refresh(zona)
    return zona