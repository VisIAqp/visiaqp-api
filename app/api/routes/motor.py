from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.services import indicador_service
from app.api.deps import verificar_api_key_motor
from app.core.database import get_db
from app.crud import camara as crud_camara
from app.crud import procesamiento as crud_proc
from app.crud import resultado_deteccion as crud_resultado
from app.schemas.camara import CamaraMotor
from app.schemas.procesamiento import (
    ProcesamientoCerrado,
    ProcesamientoCierre,
    ProcesamientoCreado,
    ProcesamientoCreate,
)
from app.schemas.resultado_deteccion import ResultadoCreado, ResultadoCreate
from app.crud import video as crud_video
from app.schemas.procesamiento import PendienteMotor
from app.schemas.video import SincronizarRequest, SincronizarResultado

logger = logging.getLogger(__name__)

# Contrato con visiaqp-ai: NO cambiar rutas ni payloads sin avisar.
router = APIRouter(tags=["motor"], dependencies=[Depends(verificar_api_key_motor)])


@router.get("/camaras", response_model=list[CamaraMotor])
def listar_camaras(db: Session = Depends(get_db)):
    return crud_camara.listar_activas(db)


@router.post(
    "/procesamientos",
    response_model=ProcesamientoCreado,
    status_code=status.HTTP_201_CREATED,
)
def crear_procesamiento(datos: ProcesamientoCreate, db: Session = Depends(get_db)):
    if datos.id_camara is not None:
        if not crud_camara.obtener_en_zona(db, datos.id_camara, datos.id_zona):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="La cámara no existe o no pertenece a la zona indicada",
            )
    proc = crud_proc.crear(db, datos)
    return {"id_procesamiento": proc.id_procesamiento}


@router.post(
    "/procesamientos/{id_procesamiento}/resultados",
    response_model=ResultadoCreado,
    status_code=status.HTTP_201_CREATED,
)
def registrar_resultado(
    id_procesamiento: int, datos: ResultadoCreate, db: Session = Depends(get_db)
):
    proc = crud_proc.obtener(db, id_procesamiento)
    if not proc:
        raise HTTPException(status_code=404, detail="Procesamiento no encontrado")
    if proc.estado != "procesando":
        raise HTTPException(
            status_code=409,
            detail=f"El procesamiento está en estado '{proc.estado}', no acepta resultados",
        )
    if datos.id_zona != proc.id_zona or (
        datos.id_camara is not None and datos.id_camara != proc.id_camara
    ):
        raise HTTPException(
            status_code=422,
            detail="id_zona/id_camara no coinciden con el procesamiento",
        )

    id_zona = proc.id_zona  # se lee antes del commit, que expira el objeto
    resultado = crud_resultado.crear(db, id_procesamiento, datos)
    id_resultado = resultado.id_resultado

    # El resultado ya está guardado: si el recálculo falla no se rompe el contrato con el motor
    try:
        indicador_service.actualizar_indicadores(
            db, id_zona, datos.periodo_inicio.replace(microsecond=0)
        )
    except Exception:
        db.rollback()
        logger.exception("Falló el recálculo de indicadores (zona %s)", id_zona)

    return {"id_resultado": id_resultado}


@router.patch("/procesamientos/{id_procesamiento}", response_model=ProcesamientoCerrado)
def cerrar_procesamiento(
    id_procesamiento: int, datos: ProcesamientoCierre, db: Session = Depends(get_db)
):
    proc = crud_proc.obtener(db, id_procesamiento)
    if not proc:
        raise HTTPException(status_code=404, detail="Procesamiento no encontrado")
    proc = crud_proc.cerrar(db, proc, datos)
    return {"id_procesamiento": proc.id_procesamiento, "estado": proc.estado}


@router.post("/videos/sincronizar", response_model=SincronizarResultado)
def sincronizar_videos(datos: SincronizarRequest, db: Session = Depends(get_db)):
    return crud_video.sincronizar(db, datos.videos)


@router.get("/procesamientos/pendientes", response_model=list[PendienteMotor])
def listar_pendientes(db: Session = Depends(get_db)):
    return [
        PendienteMotor(
            id_procesamiento=p.id_procesamiento,
            id_zona=p.id_zona,
            id_camara=p.id_camara,
            nombre_camara=nombre_camara,
            nombre_archivo=p.ruta_archivo or "",
            fecha_captura_inicio=p.fecha_captura_inicio,
            zone_polygon=poligono,
        )
        for p, nombre_camara, poligono in crud_proc.listar_pendientes(db)
    ]


@router.patch(
    "/procesamientos/{id_procesamiento}/iniciar", response_model=ProcesamientoCerrado
)
def iniciar_procesamiento(id_procesamiento: int, db: Session = Depends(get_db)):
    if crud_proc.reclamar(db, id_procesamiento):
        return {"id_procesamiento": id_procesamiento, "estado": "procesando"}
    if crud_proc.obtener(db, id_procesamiento) is None:
        raise HTTPException(status_code=404, detail="Procesamiento no encontrado")
    raise HTTPException(status_code=409, detail="El procesamiento ya no está pendiente")