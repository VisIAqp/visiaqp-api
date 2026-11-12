"""Métricas autenticadas con filtros acotados y paginación explícita."""
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.tiempo import ahora_lima
from app.crud import metricas, procesamiento
from app.models.camara import Camara
from app.models.procesamiento import Procesamiento
from app.models.zona import Zona
from app.schemas.metricas import (
    DistribucionNivel, FiltrosMetricas, MedicionAgregada, PaginaCamaras,
    PaginaMetricas, PatronHorario, PuntoSerie, ResumenMetricas,
)

router = APIRouter(prefix='/metricas', tags=['metricas'], dependencies=[Depends(get_current_user)])


def validar_ubicacion(db, id_zona, id_camara):
    if id_zona is not None and db.get(Zona, id_zona) is None:
        raise HTTPException(status_code=404, detail='Zona no encontrada')
    if id_camara is not None:
        camara = db.get(Camara, id_camara)
        if camara is None:
            raise HTTPException(status_code=404, detail='Cámara no encontrada')
        if id_zona is not None and camara.id_zona != id_zona:
            raise HTTPException(status_code=422, detail='La cámara no pertenece a la zona indicada')


def filtros(
    desde: datetime | None = None, hasta: datetime | None = None,
    periodo: Literal['hora', 'dia'] = 'hora',
    id_zona: int | None = Query(default=None, ge=1),
    id_camara: int | None = Query(default=None, ge=1),
    id_procesamiento: int | None = Query(default=None, ge=1),
    tipo_fuente: Literal['imagen', 'video', 'stream'] | None = None,
    db: Session = Depends(get_db),
):
    hasta = hasta or ahora_lima()
    if hasta.year < 1000:
        raise HTTPException(status_code=422, detail='Las fechas deben pertenecer al rango DATETIME de MySQL, desde el año 1000')
    desde = desde or hasta - timedelta(days=7)
    if desde.year < 1000:
        raise HTTPException(status_code=422, detail='Las fechas deben pertenecer al rango DATETIME de MySQL, desde el año 1000')
    if desde.tzinfo is not None or hasta.tzinfo is not None:
        raise HTTPException(status_code=422, detail='Envía las fechas en hora de Lima, sin zona horaria explícita')
    if hasta <= desde or hasta - desde > timedelta(days=31):
        raise HTTPException(status_code=422, detail='El rango debe ser positivo y no superar 31 días')
    validar_ubicacion(db, id_zona, id_camara)
    if id_procesamiento is not None:
        proc = db.get(Procesamiento, id_procesamiento)
        if proc is None:
            raise HTTPException(status_code=404, detail='Procesamiento no encontrado')
        if ((id_zona is not None and proc.id_zona != id_zona) or
            (id_camara is not None and proc.id_camara != id_camara) or
            (tipo_fuente is not None and proc.tipo_fuente != tipo_fuente)):
            raise HTTPException(status_code=422, detail='Los filtros no corresponden al procesamiento')
    return FiltrosMetricas(desde=desde, hasta=hasta, periodo=periodo, id_zona=id_zona,
                          id_camara=id_camara, id_procesamiento=id_procesamiento,
                          tipo_fuente=tipo_fuente)


def contexto(f):
    return dict(desde=f.desde, hasta=f.hasta, consultado_en=ahora_lima())


@router.get('/resumen', response_model=ResumenMetricas)
def resumen(f: FiltrosMetricas = Depends(filtros), db: Session = Depends(get_db)):
    """Conteos del rango y estado operativo actual; no suma ocupación entre zonas."""
    procesamiento.expirar_inactivos(db)
    return {**contexto(f), **metricas.resumen(db, f)}


@router.get('/series', response_model=PaginaMetricas[PuntoSerie])
def series(f: FiltrosMetricas = Depends(filtros), limite: int = Query(default=500, ge=1, le=1000),
           desplazamiento: int = Query(default=0, ge=0), db: Session = Depends(get_db)):
    """Una serie por zona, cámara, fuente y ejecución. No rellena huecos con ceros."""
    return {**contexto(f), **metricas.paginar(db, metricas.series(f),
        ['periodo_inicio', 'id_zona', 'id_camara', 'id_procesamiento'], limite, desplazamiento)}


@router.get('/comparativas', response_model=PaginaMetricas[MedicionAgregada])
def comparativas(f: FiltrosMetricas = Depends(filtros), limite: int = Query(default=500, ge=1, le=1000),
                 desplazamiento: int = Query(default=0, ge=0), db: Session = Depends(get_db)):
    """Zonas con resultados; varias ejecuciones o vistas no se fusionan automáticamente."""
    return {**contexto(f), **metricas.paginar(db, metricas.comparativas(f),
        ['id_zona'], limite, desplazamiento)}


@router.get('/patrones', response_model=PaginaMetricas[PatronHorario])
def patrones(f: FiltrosMetricas = Depends(filtros), limite: int = Query(default=500, ge=1, le=1000),
             desplazamiento: int = Query(default=0, ge=0), db: Session = Depends(get_db)):
    """Mapa de calor por zona, día de semana (lunes=0) y hora de captura."""
    return {**contexto(f), **metricas.paginar(db, metricas.patrones(f),
        ['id_zona', 'dia_semana', 'hora'], limite, desplazamiento)}


@router.get('/distribucion-niveles', response_model=PaginaMetricas[DistribucionNivel])
def distribucion(f: FiltrosMetricas = Depends(filtros), limite: int = Query(default=500, ge=1, le=1000),
                  desplazamiento: int = Query(default=0, ge=0), db: Session = Depends(get_db)):
    """Cantidad de periodos de cada serie por nivel y estado, sin clasificar ausencias como bajo."""
    return {**contexto(f), **metricas.paginar(db, metricas.distribucion(f),
        ['id_zona', 'estado_ocupacion', 'nivel_ocupacion'], limite, desplazamiento)}


@router.get('/estado-camaras', response_model=PaginaCamaras)
def estado_camaras(id_zona: int | None = Query(default=None, ge=1),
                   id_camara: int | None = Query(default=None, ge=1),
                   limite: int = Query(default=500, ge=1, le=1000),
                   desplazamiento: int = Query(default=0, ge=0), db: Session = Depends(get_db)):
    """Estado actual sobre la última transmisión de cada cámara; no expone URLs."""
    validar_ubicacion(db, id_zona, id_camara)
    procesamiento.expirar_inactivos(db)
    ahora = ahora_lima()
    return dict(consultado_en=ahora, inactividad_limite_seg=settings.MOTOR_INACTIVIDAD_SEG,
                **metricas.paginar(db, metricas.estado_camaras(id_zona, id_camara, ahora),
                                  ['id_camara'], limite, desplazamiento))
