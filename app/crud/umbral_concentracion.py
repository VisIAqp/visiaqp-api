from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.umbral_concentracion import UmbralConcentracion
from app.schemas.umbral_concentracion import UmbralIn


def obtener(db: Session, id_zona: int) -> UmbralConcentracion | None:
    return db.scalars(
        select(UmbralConcentracion).where(UmbralConcentracion.id_zona == id_zona)
    ).first()


def guardar(db: Session, id_zona: int, datos: UmbralIn) -> UmbralConcentracion:
    umbral = obtener(db, id_zona)
    if umbral is None:
        umbral = UmbralConcentracion(id_zona=id_zona, **datos.model_dump())
        db.add(umbral)
    else:
        umbral.umbral_medio = datos.umbral_medio
        umbral.umbral_alto = datos.umbral_alto
    db.commit()
    db.refresh(umbral)
    return umbral