from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.camara import Camara
from app.core.config import settings
from app.models.procesamiento import Procesamiento
from app.schemas.procesamiento import ProcesamientoCierre, ProcesamientoCreate
from sqlalchemy import func, select, update

def obtener(db: Session, id_procesamiento: int) -> Procesamiento | None:
    return db.get(Procesamiento, id_procesamiento)


def crear(db: Session, datos: ProcesamientoCreate) -> Procesamiento:
    # La fila de cámara serializa las reservas entre procesos e instancias.
    if datos.tipo_fuente == "stream":
        if datos.id_camara is None:
            raise ValueError("Una transmisión requiere cámara")
        camara_reservada = db.scalar(select(Camara).where(Camara.id_camara == datos.id_camara).with_for_update())
        if camara_reservada is None or camara_reservada.estado != "activa":
            raise ValueError("La cámara no está habilitada")
        _expirar(db, datos.id_camara)
        activo = db.scalar(select(Procesamiento.id_procesamiento).where(
            Procesamiento.id_camara == datos.id_camara,
            Procesamiento.tipo_fuente == "stream", Procesamiento.estado == "procesando",
        ).with_for_update())
        if activo is not None:
            raise ValueError("La cámara ya está reservada por un motor activo")
    proc = Procesamiento(**datos.model_dump(), estado="procesando", ultima_actividad=datetime.now())
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
    if proc.estado != "procesando":
        # Un trabajador antiguo no puede convertir una ejecución vencida en éxito.
        return proc
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
    expirar_inactivos(db)
    stmt = (
        select(Procesamiento, Camara.nombre, Camara.zone_polygon, Camara.intervalo_muestreo_seg)
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
        .values(estado="procesando", fecha_inicio_proceso=func.now(), ultima_actividad=func.now())
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
    expirar_inactivos(db)
    stmt = select(Procesamiento)
    if estado:
        stmt = stmt.where(Procesamiento.estado == estado)
    if id_camara is not None:
        stmt = stmt.where(Procesamiento.id_camara == id_camara)
    stmt = stmt.order_by(Procesamiento.id_procesamiento.desc()).limit(limite)
    return list(db.scalars(stmt))

def _expirar(db: Session, id_camara: int | None = None):
    ahora = datetime.now()
    stmt = update(Procesamiento).where(
        Procesamiento.estado == "procesando",
        func.coalesce(Procesamiento.ultima_actividad, Procesamiento.fecha_inicio_proceso)
        < ahora - timedelta(seconds=settings.MOTOR_INACTIVIDAD_SEG),
    )
    if id_camara is not None:
        stmt = stmt.where(Procesamiento.id_camara == id_camara)
    db.execute(stmt.values(estado="error", fecha_fin_proceso=func.greatest(ahora, Procesamiento.fecha_inicio_proceso),
                           mensaje_error="Motor sin actividad: reserva vencida"))


def expirar_inactivos(db: Session):
    _expirar(db)
    db.commit()


def obtener_vigente(db: Session, id_procesamiento: int):
    referencia = db.execute(select(Procesamiento.id_camara, Procesamiento.tipo_fuente).where(
        Procesamiento.id_procesamiento == id_procesamiento)).first()
    if referencia and referencia.tipo_fuente == "stream" and referencia.id_camara is not None:
        # Mismo orden que crear(): cámara antes de procesamiento, para evitar interbloqueos.
        db.scalar(select(Camara).where(Camara.id_camara == referencia.id_camara).with_for_update())
    proc = db.scalar(select(Procesamiento).where(
        Procesamiento.id_procesamiento == id_procesamiento).with_for_update().execution_options(populate_existing=True))
    if proc and proc.estado == "procesando":
        ultima = proc.ultima_actividad or proc.fecha_inicio_proceso
        if (datetime.now() - ultima).total_seconds() > settings.MOTOR_INACTIVIDAD_SEG:
            proc.estado = "error"
            proc.fecha_fin_proceso = max(datetime.now(), proc.fecha_inicio_proceso)
            proc.mensaje_error = "Motor sin actividad: reserva vencida"
            db.commit()
    return proc


def registrar_actividad(db: Session, proc: Procesamiento, datos=None):
    proc.ultima_actividad = datetime.now()
    if datos:
        for campo, valor in datos.model_dump(exclude_none=True).items():
            setattr(proc, campo, valor)
    if proc.id_camara is not None and proc.tipo_fuente == "stream":
        db.execute(update(Camara).where(Camara.id_camara == proc.id_camara)
                   .values(ultima_conexion=proc.ultima_actividad))
