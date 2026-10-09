from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.camara import Camara


def listar_activas(db: Session) -> list[Camara]:
    stmt = select(Camara).where(Camara.estado == "activa").order_by(Camara.id_camara)
    return list(db.scalars(stmt))


def obtener_en_zona(db: Session, id_camara: int, id_zona: int) -> Camara | None:
    """Devuelve la cámara solo si pertenece a esa zona."""
    stmt = select(Camara).where(
        Camara.id_camara == id_camara, Camara.id_zona == id_zona
    )
    return db.scalars(stmt).first()