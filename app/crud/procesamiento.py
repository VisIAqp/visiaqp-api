from datetime import datetime

from sqlalchemy.orm import Session

from app.models.camara import Camara
from app.models.procesamiento import Procesamiento
from app.schemas.procesamiento import ProcesamientoCierre, ProcesamientoCreate
from sqlalchemy import func, select, update

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


def listar_pendientes(db: Session):
    """Filas (Procesamiento, nombre_camara, zone_polygon), del más antiguo al más reciente."""
    stmt = (
        select(Procesamiento, Camara.nombre, Camara.zone_polygon)
        .join(Camara, Camara.id_camara == Procesamiento.id_camara)
        .where(Procesamiento.estado == "pendiente", Procesamiento.tipo_fuente == "video")
        .order_by(Procesamiento.fecha_registro, Procesamiento.id_procesamiento)
    )
    return db.execute(stmt).all()


def reclamar(db: Session, id_procesamiento: int) -> bool:
    """pendiente -> procesando de forma atómica. False si ya no estaba pendiente."""
    res = db.execute(
        update(Procesamiento)
        .where(
            Procesamiento.id_procesamiento == id_procesamiento,
            Procesamiento.estado == "pendiente",
        )
        .values(estado="procesando", fecha_inicio_proceso=func.now())
    )
    db.commit()
    return res.rowcount == 1


def cancelar(db: Session, id_procesamiento: int) -> bool:
    """Solo cancela pendientes. Se registra como 'error' con un mensaje claro."""
    res = db.execute(
        update(Procesamiento)
        .where(
            Procesamiento.id_procesamiento == id_procesamiento,
            Procesamiento.estado == "pendiente",
        )
        .values(
            estado="error",
            mensaje_error="Cancelado por el usuario",
            fecha_fin_proceso=func.now(),
        )
    )
    db.commit()
    return res.rowcount == 1


def existe_activo(db: Session, id_camara: int, nombre_archivo: str) -> bool:
    stmt = select(Procesamiento.id_procesamiento).where(
        Procesamiento.tipo_fuente == "video",
        Procesamiento.id_camara == id_camara,
        Procesamiento.ruta_archivo == nombre_archivo,
        Procesamiento.estado.in_(["pendiente", "procesando"]),
    )
    return db.scalars(stmt).first() is not None


def crear_solicitud(
    db: Session,
    camara: Camara,
    nombre_archivo: str,
    id_usuario: int,
    fecha_captura: datetime,
) -> Procesamiento:
    proc = Procesamiento(
        id_zona=camara.id_zona,
        id_camara=camara.id_camara,
        id_usuario=id_usuario,
        tipo_fuente="video",
        ruta_archivo=nombre_archivo,
        fecha_captura_inicio=fecha_captura,
        estado="pendiente",
    )
    db.add(proc)
    db.commit()
    db.refresh(proc)
    return proc


def listar(
    db: Session, estado: str | None, id_camara: int | None, limite: int
) -> list[Procesamiento]:
    stmt = select(Procesamiento)
    if estado:
        stmt = stmt.where(Procesamiento.estado == estado)
    if id_camara is not None:
        stmt = stmt.where(Procesamiento.id_camara == id_camara)
    stmt = stmt.order_by(Procesamiento.id_procesamiento.desc()).limit(limite)
    return list(db.scalars(stmt))