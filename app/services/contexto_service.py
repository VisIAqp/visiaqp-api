"""Sincronización explícita, reutilización de datos y conservación ante fallos."""
import hashlib
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.dialects.mysql import insert

from app.models.contexto import ClimaHora, EventoCalendario, SincronizacionContexto
from app.services import contexto_proveedores as proveedores


def reservar(db, clave, proveedor, vigencia):
    ahora = datetime.now()
    nuevo = insert(SincronizacionContexto).values(clave=clave, proveedor=proveedor,
        ultimo_intento=datetime(1970, 1, 1), estado='pendiente')
    db.execute(nuevo.on_duplicate_key_update(clave=nuevo.inserted.clave))
    fila = db.scalar(select(SincronizacionContexto).where(SincronizacionContexto.clave == clave).with_for_update())
    if fila.estado == 'correcto' and fila.ultimo_exito and ahora - fila.ultimo_exito < vigencia:
        db.commit()
        return False
    if ahora - fila.ultimo_intento < timedelta(seconds=60):
        db.rollback()
        raise HTTPException(status_code=429, detail='Espera un minuto antes de volver a sincronizar esta consulta')
    fila.ultimo_intento, fila.estado, fila.detalle = ahora, 'en_curso', None
    db.commit()
    return True


def terminar(db, clave, error=None):
    fila = db.get(SincronizacionContexto, clave)
    fila.estado = 'error' if error else 'correcto'
    fila.detalle = str(error)[:250] if error else None
    if error is None:
        fila.ultimo_exito = datetime.now()
    db.commit()


def clave_clima(zona, desde, hasta):
    return f'clima:{zona.id_zona}:{zona.latitud}:{zona.longitud}:{desde}:{hasta}'


def sincronizar_clima(db, zona, desde, hasta):
    clave = clave_clima(zona, desde, hasta)
    if not reservar(db, clave, 'open_meteo', timedelta(hours=1)):
        return dict(estado='cache', registros=0, consultado_en=datetime.now())
    try:
        filas = proveedores.clima_por_rango(zona.latitud, zona.longitud, desde, hasta)
        ahora = datetime.now()
        for fila in filas:
            sentencia = insert(ClimaHora).values(**fila, id_zona=zona.id_zona,
                latitud=zona.latitud, longitud=zona.longitud, fuente='open_meteo', consultado_en=ahora)
            campos = {n: getattr(sentencia.inserted, n) for n in (
                'temperatura_c', 'precipitacion_mm', 'humedad_porcentaje', 'codigo_tiempo',
                'modelo', 'consultado_en', 'latitud_modelo', 'longitud_modelo')}
            db.execute(sentencia.on_duplicate_key_update(**campos))
        terminar(db, clave)
        return dict(estado='actualizado', registros=len(filas), consultado_en=ahora)
    except Exception as error:
        db.rollback()
        mensaje = str(error) if isinstance(error, proveedores.ErrorProveedor) else 'No se pudo guardar el contexto climático'
        terminar(db, clave, mensaje)
        raise HTTPException(status_code=503, detail=mensaje + '. Los datos anteriores se conservan') from None


def sincronizar_calendario(db, anio):
    clave = f'calendario:PE:{anio}'
    if not reservar(db, clave, 'nager_date', timedelta(hours=24)):
        return dict(estado='cache', registros=0, consultado_en=datetime.now())
    try:
        eventos = proveedores.feriados_peru(anio)
        db.execute(update(EventoCalendario).where(EventoCalendario.fuente == 'nager_date_v3',
            EventoCalendario.fecha >= datetime(anio, 1, 1).date(),
            EventoCalendario.fecha < datetime(anio + 1, 1, 1).date()).values(activo=False))
        for evento in eventos:
            identidad = hashlib.sha256(f"PE:{evento['fecha']}:{evento['nombre']}".encode('utf-8')).hexdigest()
            sentencia = insert(EventoCalendario).values(**{k: v for k, v in evento.items() if k != 'tipo'}, clave_externa=identidad,
                tipo=evento.get('tipo', 'feriado'), alcance='nacional', id_zona=None, fuente='nager_date_v3',
                referencia=f'https://date.nager.at/api/v3/PublicHolidays/{anio}/PE',
                activo=True, actualizado_en=datetime.now())
            db.execute(sentencia.on_duplicate_key_update(activo=True, nombre=sentencia.inserted.nombre, tipo=sentencia.inserted.tipo,
                                                        actualizado_en=sentencia.inserted.actualizado_en))
        terminar(db, clave)
        return dict(estado='actualizado', registros=len(eventos), consultado_en=datetime.now())
    except Exception as error:
        db.rollback()
        mensaje = str(error) if isinstance(error, proveedores.ErrorProveedor) else 'No se pudo guardar el calendario'
        terminar(db, clave, mensaje)
        raise HTTPException(status_code=503, detail=mensaje + '. El calendario anterior se conserva') from None
