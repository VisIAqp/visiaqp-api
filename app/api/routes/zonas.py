import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.crud import umbral_concentracion as crud_umbral
from app.crud import zona as crud_zona
from app.schemas.umbral_concentracion import UmbralIn, UmbralOut
from app.schemas.zona import ZonaCreate, ZonaOut, ZonaUpdate
from app.services import indicador_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/zonas", tags=["zonas"], dependencies=[Depends(get_current_user)]
)

# Ventana de recálculo tras cambiar un umbral
HORAS_RECALCULO = 48


def _zona_o_404(db: Session, id_zona: int):
    zona = crud_zona.obtener(db, id_zona)
    if zona is None:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    return zona


@router.get("", response_model=list[ZonaOut])
def listar_zonas(solo_activas: bool = False, db: Session = Depends(get_db)):
    return crud_zona.listar(db, solo_activas)


@router.get("/{id_zona}", response_model=ZonaOut)
def obtener_zona(id_zona: int, db: Session = Depends(get_db)):
    return _zona_o_404(db, id_zona)


@router.post(
    "",
    response_model=ZonaOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def crear_zona(datos: ZonaCreate, db: Session = Depends(get_db)):
    if crud_zona.obtener_por_nombre(db, datos.nombre):
        raise HTTPException(status_code=409, detail="Ya existe una zona con ese nombre")
    return crud_zona.crear(db, datos)


@router.patch(
    "/{id_zona}", response_model=ZonaOut, dependencies=[Depends(require_admin)]
)
def actualizar_zona(id_zona: int, datos: ZonaUpdate, db: Session = Depends(get_db)):
    zona = _zona_o_404(db, id_zona)
    if datos.nombre and datos.nombre != zona.nombre:
        if crud_zona.obtener_por_nombre(db, datos.nombre):
            raise HTTPException(
                status_code=409, detail="Ya existe una zona con ese nombre"
            )
    return crud_zona.actualizar(db, zona, datos)


@router.get("/{id_zona}/umbral", response_model=UmbralOut)
def obtener_umbral(id_zona: int, db: Session = Depends(get_db)):
    _zona_o_404(db, id_zona)
    umbral = crud_umbral.obtener(db, id_zona)
    if umbral is None:
        raise HTTPException(
            status_code=404,
            detail="La zona no tiene umbral configurado (se usan los valores por defecto)",
        )
    return umbral


@router.put(
    "/{id_zona}/umbral", response_model=UmbralOut, dependencies=[Depends(require_admin)]
)
def guardar_umbral(id_zona: int, datos: UmbralIn, db: Session = Depends(get_db)):
    _zona_o_404(db, id_zona)
    umbral = crud_umbral.guardar(db, id_zona, datos)
    id_zona_umbral = umbral.id_zona

    # El umbral ya está guardado: si el recálculo falla, no se revierte
    try:
        hasta = datetime.now() + timedelta(hours=1)
        desde = hasta - timedelta(hours=HORAS_RECALCULO)
        indicador_service.recalcular_rango(db, id_zona_umbral, desde, hasta)
    except Exception:
        db.rollback()
        logger.exception("Falló el recálculo tras cambiar el umbral (zona %s)", id_zona)

    return crud_umbral.obtener(db, id_zona)