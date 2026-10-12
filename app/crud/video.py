from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.video_disponible import VideoDisponible
from app.schemas.video import VideoSync


def listar(db: Session, solo_disponibles: bool = True) -> list[VideoDisponible]:
    stmt = select(VideoDisponible).order_by(
        VideoDisponible.fecha_modificacion.desc(), VideoDisponible.nombre_archivo
    )
    if solo_disponibles:
        stmt = stmt.where(VideoDisponible.disponible.is_(True))
    return list(db.scalars(stmt))


def sincronizar(db: Session, videos: list[VideoSync]) -> dict:
    """Recibe la lista COMPLETA de archivos del motor. Upsert + marca como no
    disponibles los que ya no vienen."""
    ahora = datetime.now()
    recibidos = {v.nombre_archivo: v for v in videos}  # si se repite, gana el último
    existentes = {v.nombre_archivo: v for v in db.scalars(select(VideoDisponible))}

    registrados = actualizados = no_disponibles = 0

    for nombre, v in recibidos.items():
        fila = existentes.get(nombre)
        if fila is None:
            db.add(
                VideoDisponible(
                    nombre_archivo=nombre,
                    tamano_bytes=v.tamano_bytes,
                    fecha_modificacion=v.fecha_modificacion,
                    disponible=True,
                    fecha_ultima_sincronizacion=ahora,
                )
            )
            registrados += 1
            continue

        if (
            fila.tamano_bytes != v.tamano_bytes
            or fila.fecha_modificacion != v.fecha_modificacion
            or not fila.disponible
        ):
            actualizados += 1
        fila.tamano_bytes = v.tamano_bytes
        fila.fecha_modificacion = v.fecha_modificacion
        fila.disponible = True
        fila.fecha_ultima_sincronizacion = ahora

    for nombre, fila in existentes.items():
        if nombre not in recibidos and fila.disponible:
            fila.disponible = False
            no_disponibles += 1

    db.commit()
    return {
        "registrados": registrados,
        "actualizados": actualizados,
        "no_disponibles": no_disponibles,
    }