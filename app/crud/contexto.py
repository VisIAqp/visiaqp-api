"""Consultas guardadas y cruce por hora de captura, sin multiplicar ventanas por feriado."""
from datetime import datetime, time, timedelta

from sqlalchemy import case, func, or_, select

from app.crud import metricas
from app.models.contexto import ClimaHora, EventoCalendario
from app.models.zona import Zona


def clima_guardado(zona, desde, hasta):
    c = ClimaHora
    seleccion = select(c, func.row_number().over(partition_by=c.hora,
        order_by=[case((c.tipo_dato == 'historico_modelado', 0), else_=1), c.consultado_en.desc()]).label('prioridad'))
    seleccion = seleccion.where(c.id_zona == zona.id_zona, c.latitud == zona.latitud, c.longitud == zona.longitud,
        c.hora >= datetime.combine(desde, time.min), c.hora < datetime.combine(hasta + timedelta(days=1), time.min))
    sub = seleccion.subquery()
    return select(sub).where(sub.c.prioridad == 1)


def eventos(anio, id_zona, incluir_inactivos=False):
    e = EventoCalendario
    consulta = select(e).where(e.fecha >= datetime(anio, 1, 1).date(),
        e.fecha < datetime(anio + 1, 1, 1).date(),
        or_(e.alcance == 'nacional', e.id_zona == id_zona) if id_zona is not None else e.alcance == 'nacional')
    if not incluir_inactivos:
        consulta = consulta.where(e.activo.is_(True))
    return consulta


def series_contexto(f):
    s = metricas.series(f).subquery()
    z = Zona
    c = ClimaHora
    orden = select(c, func.row_number().over(
        partition_by=[c.id_zona, c.hora, c.latitud, c.longitud],
        order_by=[case((c.tipo_dato == 'historico_modelado', 0), else_=1), c.consultado_en.desc()]).label('prioridad'))
    orden = orden.where(c.hora >= f.desde.replace(minute=0, second=0, microsecond=0), c.hora < f.hasta)
    if f.id_zona is not None:
        orden = orden.where(c.id_zona == f.id_zona)
    clima = orden.subquery()
    e = EventoCalendario
    def hay(tipo):
        return select(e.id_evento).where(e.activo.is_(True), e.tipo == tipo,
            e.fecha == func.date(s.c.periodo_inicio),
            or_(e.alcance == 'nacional', e.id_zona == s.c.id_zona)).exists().correlate(s)
    return select(*s.c,
        clima.c.temperatura_c, clima.c.precipitacion_mm, clima.c.humedad_porcentaje,
        clima.c.codigo_tiempo, clima.c.tipo_dato.label('tipo_clima'),
        clima.c.modelo.label('modelo_clima'), clima.c.consultado_en.label('clima_consultado_en'),
        hay('feriado').label('es_feriado'), hay('no_laborable').label('es_no_laborable'),
        hay('evento').label('tiene_evento'),
    ).join(z, z.id_zona == s.c.id_zona).outerjoin(clima,
        (clima.c.id_zona == s.c.id_zona) & (clima.c.hora == s.c.periodo_inicio) &
        (clima.c.latitud == z.latitud) & (clima.c.longitud == z.longitud) & (clima.c.prioridad == 1))
