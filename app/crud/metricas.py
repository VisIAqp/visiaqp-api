"""Agregación y paginación en MySQL, sin cargar ventanas para sumarlas en Python."""

from sqlalchemy import case, func, literal, select, text

from app.core.tiempo import ahora_lima
from app.models.camara import Camara
from app.models.procesamiento import Procesamiento
from app.models.resultado_deteccion import ResultadoDeteccion
from app.models.umbral_concentracion import UmbralConcentracion
from app.models.zona import Zona


def base_ventanas(f):
    r, p = ResultadoDeteccion, Procesamiento
    consulta = select(
        p.id_zona, p.id_camara, p.id_procesamiento, p.tipo_fuente,
        r.periodo_inicio, r.periodo_fin, r.fecha_registro, r.cantidad_peatones,
        r.promedio_presentes, r.max_presentes, r.segundos_observados,
    ).join(p, p.id_procesamiento == r.id_procesamiento).where(
        r.periodo_inicio >= f.desde, r.periodo_inicio < f.hasta,
    )
    for nombre in ('id_zona', 'id_camara', 'id_procesamiento', 'tipo_fuente'):
        valor = getattr(f, nombre)
        if valor is not None:
            consulta = consulta.where(getattr(p, nombre) == valor)
    return consulta.subquery()


def periodo(inicio, tipo):
    formato = '%Y-%m-%d %H:00:00' if tipo == 'hora' else '%Y-%m-%d 00:00:00'
    return func.str_to_date(func.date_format(inicio, formato), '%Y-%m-%d %H:%i:%s')


def agrupar(base, claves):
    c = base.c
    return select(
        *claves,
        func.count().label('cantidad_ventanas'),
        func.sum(c.cantidad_peatones).label('suma_identificadores'),
        func.count(c.promedio_presentes).label('ventanas_con_ocupacion'),
        func.count(func.distinct(c.id_camara)).label('camaras_distintas'),
        func.count(c.id_camara).label('con_camara'),
        func.count(func.distinct(c.id_procesamiento)).label('procesamientos_distintos'),
        func.count(func.distinct(c.tipo_fuente)).label('fuentes_distintas'),
        func.min(c.periodo_inicio).label('primera_ventana_inicio'),
        func.max(c.periodo_fin).label('ultima_ventana_fin'),
        func.max(c.fecha_registro).label('ultima_recepcion'),
        func.sum(c.promedio_presentes * c.segundos_observados).label('personas_segundo'),
        func.sum(c.segundos_observados).label('segundos'),
        func.max(c.max_presentes).label('pico'),
    ).group_by(*claves).subquery()


def mediciones(agregado, tipo=None):
    a = agregado.c
    estado = case(
        (a.ventanas_con_ocupacion == 0, 'sin_datos'),
        ((a.camaras_distintas != 1) | (a.con_camara != a.cantidad_ventanas) |
         (a.fuentes_distintas != 1), 'fuentes_sin_consolidar'),
        (a.procesamientos_distintos != 1, 'ejecuciones_sin_consolidar'),
        (a.ventanas_con_ocupacion != a.cantidad_ventanas, 'datos_incompletos'),
        else_='disponible',
    )
    promedio = func.round(a.personas_segundo / func.nullif(a.segundos, 0), 4)
    valido = (estado == 'disponible') & (a.segundos > 0)
    nivel = case(
        (promedio >= func.coalesce(UmbralConcentracion.umbral_alto, 30), 'alto'),
        (promedio >= func.coalesce(UmbralConcentracion.umbral_medio, 10), 'medio'),
        else_='bajo',
    )
    nombres = ('id_zona', 'id_camara', 'id_procesamiento', 'tipo_fuente',
               'periodo_inicio', 'dia_semana', 'hora', 'cantidad_ventanas',
               'suma_identificadores', 'ventanas_con_ocupacion', 'camaras_distintas',
               'procesamientos_distintos', 'primera_ventana_inicio', 'ultima_ventana_fin', 'ultima_recepcion')
    columnas = [a[n] for n in nombres if n in a]
    if tipo:
        intervalo = text('INTERVAL 1 HOUR' if tipo == 'hora' else 'INTERVAL 1 DAY')
        fin_periodo = func.date_add(a.periodo_inicio, intervalo)
        columnas.append(fin_periodo.label('periodo_fin'))
        columnas.append((fin_periodo <= ahora_lima()).label('periodo_cerrado'))
    return select(
        *columnas, Zona.nombre.label('nombre_zona'),
        case((valido, promedio), else_=None).label('promedio_presentes'),
        case((valido, a.pico), else_=None).label('max_presentes'),
        case((valido, a.segundos), else_=None).label('segundos_observados'),
        case((valido, nivel), else_=None).label('nivel_ocupacion'),
        estado.label('estado_ocupacion'),
    ).join(Zona, Zona.id_zona == a.id_zona).outerjoin(
        UmbralConcentracion, UmbralConcentracion.id_zona == a.id_zona,
    )


def series(f):
    b = base_ventanas(f)
    claves = [b.c.id_zona, b.c.id_camara, b.c.id_procesamiento, b.c.tipo_fuente,
              periodo(b.c.periodo_inicio, f.periodo).label('periodo_inicio')]
    return mediciones(agrupar(b, claves), f.periodo)


def comparativas(f):
    b = base_ventanas(f)
    return mediciones(agrupar(b, [b.c.id_zona]))


def patrones(f):
    b = base_ventanas(f)
    return mediciones(agrupar(b, [b.c.id_zona,
        func.weekday(b.c.periodo_inicio).label('dia_semana'),
        func.hour(b.c.periodo_inicio).label('hora')]))


def distribucion(f):
    b = series(f).subquery()
    return select(b.c.id_zona, b.c.nombre_zona, b.c.nivel_ocupacion,
                  b.c.estado_ocupacion, func.count().label('cantidad_periodos')).group_by(
        b.c.id_zona, b.c.nombre_zona, b.c.nivel_ocupacion, b.c.estado_ocupacion)


def paginar(db, consulta, orden, limite, desplazamiento):
    subconsulta = consulta.subquery()
    total = db.scalar(select(func.count()).select_from(subconsulta))
    filas = db.execute(select(subconsulta).order_by(*[subconsulta.c[n] for n in orden])
                       .limit(limite).offset(desplazamiento)).mappings().all()
    return dict(total=total, limite=limite, desplazamiento=desplazamiento,
                tiene_mas=desplazamiento + len(filas) < total, datos=filas)


def resumen(db, f):
    b = base_ventanas(f).c
    datos = dict(db.execute(select(
        func.count().label('cantidad_ventanas'),
        func.coalesce(func.sum(b.cantidad_peatones), 0).label('suma_identificadores'),
        func.count(b.promedio_presentes).label('ventanas_con_ocupacion'),
        func.count(func.distinct(b.id_zona)).label('zonas_con_resultados'),
        func.count(func.distinct(b.id_camara)).label('camaras_con_resultados'),
        func.count(func.distinct(b.id_procesamiento)).label('procesamientos_con_resultados'),
        func.max(b.periodo_fin).label('ultima_ventana_fin'),
        func.max(b.fecha_registro).label('ultima_recepcion'),
    )).mappings().one())
    camaras = select(Camara.id_camara, Camara.estado)
    zonas = select(Zona.id_zona, Zona.estado)
    procesos = select(Procesamiento.estado, Procesamiento.tipo_fuente,
                       Procesamiento.ultima_actividad)
    if f.id_zona is not None:
        camaras = camaras.where(Camara.id_zona == f.id_zona)
        zonas = zonas.where(Zona.id_zona == f.id_zona)
        procesos = procesos.where(Procesamiento.id_zona == f.id_zona)
    if f.id_camara is not None:
        camaras = camaras.where(Camara.id_camara == f.id_camara)
        zonas = zonas.where(Zona.id_zona == select(Camara.id_zona).where(
            Camara.id_camara == f.id_camara).scalar_subquery())
        procesos = procesos.where(Procesamiento.id_camara == f.id_camara)
    for nombre in ('id_procesamiento', 'tipo_fuente'):
        if getattr(f, nombre) is not None:
            procesos = procesos.where(getattr(Procesamiento, nombre) == getattr(f, nombre))
    c, z, p = camaras.subquery().c, zonas.subquery().c, procesos.subquery().c
    datos.update(db.execute(select(
        func.count().label('camaras_registradas'),
        func.coalesce(func.sum(case((c.estado == 'activa', 1), else_=0)), 0).label('camaras_habilitadas'),
    )).mappings().one())
    datos['zonas_activas'] = db.scalar(select(func.count()).where(z.estado == 'activa'))
    datos.update(db.execute(select(
        func.coalesce(func.sum(case((p.estado == 'procesando', 1), else_=0)), 0).label('procesamientos_en_curso'),
        func.coalesce(func.sum(case(((p.estado == 'pendiente') & (p.tipo_fuente == 'video'), 1), else_=0)), 0).label('videos_pendientes'),
        func.coalesce(func.sum(case(((p.estado == 'procesando') & (p.tipo_fuente == 'stream') & p.ultima_actividad.is_not(None), 1), else_=0)), 0).label('transmisiones_reportando'),
    )).mappings().one())
    return datos


def estado_camaras(id_zona, id_camara, ahora):
    p = select(
        Procesamiento.id_camara, Procesamiento.id_procesamiento,
        Procesamiento.estado, Procesamiento.ultima_actividad,
        Procesamiento.ultima_muestra, Procesamiento.fps_procesamiento,
        Procesamiento.retraso_seg,
        func.row_number().over(partition_by=Procesamiento.id_camara,
                               order_by=Procesamiento.id_procesamiento.desc()).label('posicion'),
    ).where(Procesamiento.tipo_fuente == 'stream').subquery()
    transmisiones = p
    p = transmisiones.c
    estado = case(
        (Camara.estado != 'activa', 'deshabilitada'),
        (p.id_procesamiento.is_(None), 'sin_transmision'),
        ((p.estado == 'procesando') & p.ultima_actividad.is_not(None), 'reportando'),
        (p.estado == 'procesando', 'sin_actividad'),
        (p.estado == 'error', 'interrumpida'), else_='finalizada',
    )
    consulta = select(
        Camara.id_camara, Camara.id_zona, Camara.nombre.label('nombre_camara'),
        Zona.nombre.label('nombre_zona'), Camara.estado.label('estado_configuracion'),
        estado.label('estado_operativo'), p.id_procesamiento, p.ultima_actividad,
        p.ultima_muestra, p.fps_procesamiento, p.retraso_seg.label('edad_imagen_seg'),
        func.greatest(0, func.timestampdiff(text('SECOND'), p.ultima_actividad, ahora)).label('segundos_sin_actividad'),
    ).join(Zona, Zona.id_zona == Camara.id_zona).outerjoin(
        transmisiones, (p.id_camara == Camara.id_camara) & (p.posicion == 1))
    if id_zona is not None:
        consulta = consulta.where(Camara.id_zona == id_zona)
    if id_camara is not None:
        consulta = consulta.where(Camara.id_camara == id_camara)
    return consulta
