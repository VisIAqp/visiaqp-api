from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.api.routes.metricas import filtros, validar_ubicacion
from app.core.database import get_db
from app.crud import contexto as consultas, metricas
from app.models.contexto import EventoCalendario, SincronizacionContexto
from app.models.zona import Zona
from app.schemas.contexto import (ClimaSalida, EstadoSincronizacion, EventoEntrada,
    EventoSalida, RangoClima, SincronizacionSalida, PaginaCalendario, PaginaClima, PaginaSeriesContexto)
from app.schemas.metricas import FiltrosMetricas
from app.services import contexto_service as servicio

router = APIRouter(prefix='/contexto', tags=['contexto'], dependencies=[Depends(get_current_user)])


def zona_peru(db, id_zona, coordenadas=False):
    zona = db.get(Zona, id_zona)
    if zona is None:
        raise HTTPException(status_code=404, detail='Zona no encontrada')
    if zona.pais != 'PE':
        raise HTTPException(status_code=422, detail='Este calendario y contexto están configurados para Perú')
    if coordenadas and (zona.latitud is None or zona.longitud is None):
        raise HTTPException(status_code=422, detail='Configura coordenadas reales de la zona antes de sincronizar clima')
    return zona


@router.get('/calendario', response_model=PaginaCalendario)
def calendario(anio: int = Query(ge=1940, le=2100), id_zona: int | None = Query(default=None, ge=1),
               limite: int = Query(default=100, ge=1, le=1000), desplazamiento: int = Query(default=0, ge=0),
               db: Session = Depends(get_db)):
    if id_zona is not None:
        zona_peru(db, id_zona)
    consulta = consultas.eventos(anio, id_zona).subquery()
    total = db.scalar(select(func.count()).select_from(consulta))
    filas = db.execute(select(consulta).order_by(consulta.c.fecha, consulta.c.id_evento)
                       .limit(limite).offset(desplazamiento)).mappings().all()
    sync = db.get(SincronizacionContexto, f'calendario:PE:{anio}')
    return dict(consultado_en=datetime.now(), zona_horaria='America/Lima', total=total,
        limite=limite, desplazamiento=desplazamiento, tiene_mas=desplazamiento + len(filas) < total,
        datos=[EventoSalida.model_validate(dict(f)).model_dump() for f in filas],
        sincronizacion=EstadoSincronizacion.model_validate(sync).model_dump() if sync else None,
        aviso='Los feriados locales y días no laborables requieren fuentes complementarias; ausencia de registro no prueba que sea laborable')


@router.post('/calendario/sincronizar', response_model=SincronizacionSalida, dependencies=[Depends(require_admin)])
def sincronizar_calendario(anio: int = Query(ge=1940, le=2100), db: Session = Depends(get_db)):
    return servicio.sincronizar_calendario(db, anio)


@router.post('/eventos', response_model=EventoSalida, status_code=201, dependencies=[Depends(require_admin)])
def crear_evento(datos: EventoEntrada, db: Session = Depends(get_db)):
    if datos.id_zona is not None:
        zona_peru(db, datos.id_zona)
    fila = EventoCalendario(**{**datos.model_dump(), 'referencia': str(datos.referencia)}, fuente='manual')
    db.add(fila)
    db.commit()
    db.refresh(fila)
    return fila


@router.put('/eventos/{id_evento}', response_model=EventoSalida, dependencies=[Depends(require_admin)])
def editar_evento(id_evento: int, datos: EventoEntrada, db: Session = Depends(get_db)):
    fila = db.get(EventoCalendario, id_evento)
    if fila is None:
        raise HTTPException(status_code=404, detail='Evento no encontrado')
    if fila.fuente != 'manual':
        raise HTTPException(status_code=409, detail='Los feriados del proveedor no se editan; registra un evento complementario con su fuente')
    if datos.id_zona is not None:
        zona_peru(db, datos.id_zona)
    for nombre, valor in {**datos.model_dump(), 'referencia': str(datos.referencia)}.items():
        setattr(fila, nombre, valor)
    db.commit()
    db.refresh(fila)
    return fila


@router.get('/clima', response_model=PaginaClima)
def clima(id_zona: int = Query(ge=1), desde: date = Query(), hasta: date = Query(),
          limite: int = Query(default=100, ge=1, le=1000), desplazamiento: int = Query(default=0, ge=0),
          db: Session = Depends(get_db)):
    validar_rango_clima(id_zona, desde, hasta)
    zona = zona_peru(db, id_zona)
    pagina = metricas.paginar(db, consultas.clima_guardado(zona, desde, hasta), ['hora'], limite, desplazamiento)
    sync = db.get(SincronizacionContexto, servicio.clave_clima(zona, desde, hasta))
    return dict(consultado_en=datetime.now(), zona_horaria='America/Lima', **{**pagina,
        'datos': [ClimaSalida.model_validate(dict(f)).model_dump() for f in pagina['datos']]},
        coordenadas_configuradas=zona.latitud is not None and zona.longitud is not None,
        sincronizacion=EstadoSincronizacion.model_validate(sync).model_dump() if sync else None,
        atribucion='Datos meteorológicos modelados de Open-Meteo · CC BY 4.0')


def validar_rango_clima(id_zona, desde, hasta):
    from pydantic import ValidationError
    try:
        return RangoClima(id_zona=id_zona, desde=desde, hasta=hasta)
    except ValidationError:
        raise HTTPException(status_code=422, detail='El clima admite de 1 a 31 días desde 1940, sin días futuros') from None


@router.post('/clima/sincronizar', response_model=SincronizacionSalida, dependencies=[Depends(require_admin)])
def sincronizar_clima(datos: RangoClima, db: Session = Depends(get_db)):
    zona = zona_peru(db, datos.id_zona, coordenadas=True)
    return servicio.sincronizar_clima(db, zona, datos.desde, datos.hasta)


@router.get('/series', response_model=PaginaSeriesContexto)
def series_contexto(f: FiltrosMetricas = Depends(filtros), limite: int = Query(default=100, ge=1, le=1000),
                   desplazamiento: int = Query(default=0, ge=0), db: Session = Depends(get_db)):
    if f.periodo != 'hora':
        raise HTTPException(status_code=422, detail='El cruce climático utiliza agrupación por hora')
    if f.id_zona is None:
        raise HTTPException(status_code=422, detail='Selecciona una zona para relacionar clima, calendario y ocupación')
    zona_peru(db, f.id_zona)
    pagina = metricas.paginar(db, consultas.series_contexto(f),
        ['periodo_inicio', 'id_procesamiento'], limite, desplazamiento)
    return dict(desde=f.desde, hasta=f.hasta, consultado_en=datetime.now(), zona_horaria='America/Lima',
        **pagina, aviso='Contexto asociado por hora de captura; no demuestra causalidad ni cobertura completa del calendario')
