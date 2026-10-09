from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.indicador import Indicador
from app.models.zona import Zona


def listar(
    db: Session,
    id_zona: int,
    periodo_tipo: str,
    desde: datetime | None,
    hasta: datetime | None,
    limite: int,
) -> list[Indicador]:
    stmt = select(Indicador).where(
        Indicador.id_zona == id_zona, Indicador.periodo_tipo == periodo_tipo
    )
    if desde:
        stmt = stmt.where(Indicador.periodo_inicio >= desde)
    if hasta:
        stmt = stmt.where(Indicador.periodo_inicio < hasta)
    stmt = stmt.order_by(Indicador.periodo_inicio).limit(limite)
    return list(db.scalars(stmt))


def actuales(db: Session, nivel: str | None = None):
    """Último indicador por hora de cada zona activa. Devuelve filas (Indicador, nombre_zona)."""
    ultimo = (
        select(
            Indicador.id_zona.label("id_zona"),
            func.max(Indicador.periodo_inicio).label("max_inicio"),
        )
        .where(Indicador.periodo_tipo == "hora")
        .group_by(Indicador.id_zona)
        .subquery()
    )
    stmt = (
        select(Indicador, Zona.nombre)
        .join(
            ultimo,
            (Indicador.id_zona == ultimo.c.id_zona)
            & (Indicador.periodo_inicio == ultimo.c.max_inicio),
        )
        .join(Zona, Zona.id_zona == Indicador.id_zona)
        .where(Indicador.periodo_tipo == "hora", Zona.estado == "activa")
    )
    if nivel:
        stmt = stmt.where(Indicador.nivel_concentracion == nivel)
    return db.execute(stmt.order_by(Zona.nombre)).all()