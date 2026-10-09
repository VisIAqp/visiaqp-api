from datetime import datetime

from sqlalchemy.orm import Session

from app.models.camara import Camara
from app.models.procesamiento import Procesamiento
from app.schemas.procesamiento import ProcesamientoCierre, ProcesamientoCreate


def obtener(db: Session, id_procesamiento: int) -> Procesamiento | None:
    return db.get(Procesamiento, id_procesamiento)


def crear(db: Session, datos: ProcesamientoCreate) -> Procesamiento:
    proc = Procesamiento(**datos.model_dump(), estado="procesando")
    db.add(proc)

    # Marca la última conexión de la cámara
    if datos.id_camara is not None:
        camara = db.get(Camara, datos.id_camara)
        if camara:
            camara.ultima_conexion = datetime.now()

    db.commit()
    db.refresh(proc)
    return proc


def cerrar(db: Session, proc: Procesamiento, datos: ProcesamientoCierre) -> Procesamiento:
    fecha_fin = datos.fecha_fin_proceso or datetime.now()
    # Evita violar el CHECK por diferencia de relojes entre motor y BD
    if fecha_fin < proc.fecha_inicio_proceso:
        fecha_fin = proc.fecha_inicio_proceso

    proc.estado = datos.estado
    proc.fecha_fin_proceso = fecha_fin
    proc.mensaje_error = datos.mensaje_error if datos.estado == "error" else None
    db.commit()
    db.refresh(proc)
    return proc