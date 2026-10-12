from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.crud import camara as crud_camara
from app.crud import procesamiento as crud_proc
from app.models.usuario import Usuario
from app.models.video_disponible import VideoDisponible
from app.schemas.procesamiento import (
    ProcesamientoCerrado,
    ProcesamientoOut,
    SolicitudCreate,
)

router = APIRouter(prefix="/procesamientos", tags=["procesamientos"])


@router.get("", response_model=list[ProcesamientoOut])
def listar_procesamientos(
    estado: Literal["pendiente", "procesando", "completado", "error"] | None = None,
    id_camara: int | None = None,
    limite: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    return crud_proc.listar(db, estado, id_camara, limite)


@router.post(
    "/solicitar", response_model=ProcesamientoOut, status_code=status.HTTP_201_CREATED
)
def solicitar_analisis(
    datos: SolicitudCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    video = db.get(VideoDisponible, datos.id_video)
    if video is None or not video.disponible:
        raise HTTPException(status_code=422, detail="El video no existe o ya no está disponible")

    camara = crud_camara.obtener(db, datos.id_camara)
    if camara is None or camara.estado != "activa":
        raise HTTPException(status_code=422, detail="La cámara no existe o no está activa")

    if datos.fecha_captura_inicio > datetime.now() + timedelta(minutes=5):
        raise HTTPException(status_code=422, detail="La fecha de captura no puede ser futura")

    if crud_proc.existe_activo(db, camara.id_camara, video.nombre_archivo):
        raise HTTPException(
            status_code=409,
            detail="Ya hay un análisis pendiente o en curso para este video y cámara",
        )

    return crud_proc.crear_solicitud(
        db, camara, video.nombre_archivo, usuario.id_usuario, datos.fecha_captura_inicio
    )


@router.patch("/{id_procesamiento}/cancelar", response_model=ProcesamientoCerrado)
def cancelar_solicitud(
    id_procesamiento: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    proc = crud_proc.obtener(db, id_procesamiento)
    if proc is None:
        raise HTTPException(status_code=404, detail="Procesamiento no encontrado")

    es_admin = usuario.rol.nombre == "Administrador"
    if not es_admin and proc.id_usuario != usuario.id_usuario:
        raise HTTPException(status_code=403, detail="Solo puedes cancelar tus propias solicitudes")

    if not crud_proc.cancelar(db, id_procesamiento):
        raise HTTPException(
            status_code=409, detail="Solo se pueden cancelar procesamientos pendientes"
        )
    return {"id_procesamiento": id_procesamiento, "estado": "error"}