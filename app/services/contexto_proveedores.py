"""Clientes públicos con hosts fijos y validación antes de guardar resultados."""
import json
import math
from datetime import date, datetime, time, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import settings


class ErrorProveedor(RuntimeError):
    pass


def obtener_json(url, parametros=None):
    if parametros:
        url += '?' + urlencode(parametros)
    try:
        solicitud = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'VisIAqp-academico/1.0'})
        with urlopen(solicitud, timeout=settings.CONTEXTO_TIMEOUT_SEG) as respuesta:
            contenido = respuesta.read(2_000_001)
        if len(contenido) > 2_000_000:
            raise ErrorProveedor('La respuesta externa supera el tamaño permitido')
        return json.loads(contenido)
    except HTTPError as error:
        raise ErrorProveedor(f'El proveedor respondió HTTP {error.code}') from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise ErrorProveedor('No se pudo obtener una respuesta válida del proveedor') from None


def feriados_peru(anio):
    datos = obtener_json(f'https://date.nager.at/api/v3/PublicHolidays/{anio}/PE')
    if not isinstance(datos, list) or not datos or len(datos) > 200:
        raise ErrorProveedor('Nager.Date no devolvió un calendario verificable para Perú')
    eventos = []
    try:
        for fila in datos:
            fecha = date.fromisoformat(fila['date'])
            nombre = fila.get('localName') or fila['name']
            if fecha.year != anio or fila['countryCode'] != 'PE' or not isinstance(nombre, str) or not 1 <= len(nombre.strip()) <= 150:
                raise ValueError()
            # No convertir feriados de una subdivisión en feriados nacionales.
            if fila.get('global') is True and 'Public' in fila.get('types', []):
                # El proveedor incluye Domingo Santo; se conserva como contexto,
                # no como un feriado nacional remunerado independiente.
                es_pascua = fila.get('name') == 'Easter Sunday' or nombre.strip() in ('Domingo Santo', 'Domingo de Resurrección')
                eventos.append({'fecha': fecha, 'nombre': nombre.strip(), 'tipo': 'evento' if es_pascua else 'feriado'})
    except (KeyError, TypeError, ValueError):
        raise ErrorProveedor('El calendario externo tiene datos inconsistentes') from None
    if not eventos:
        raise ErrorProveedor('No se recibieron feriados nacionales válidos')
    return eventos


def clima_por_rango(latitud, longitud, desde, hasta, ahora=None):
    ahora = ahora or datetime.now()
    corte = ahora.date() - timedelta(days=6)
    segmentos = []
    if desde <= corte:
        segmentos.append((desde, min(hasta, corte), 'historico_modelado', 'era5', 'https://archive-api.open-meteo.com/v1/archive'))
    if hasta > corte:
        segmentos.append((max(desde, corte + timedelta(days=1)), hasta, 'estimacion_reciente', 'automatico', 'https://api.open-meteo.com/v1/forecast'))
    filas = []
    for inicio, fin, tipo, modelo, url in segmentos:
        parametros = {'latitude': str(latitud), 'longitude': str(longitud),
            'start_date': inicio.isoformat(), 'end_date': fin.isoformat(),
            'hourly': 'temperature_2m,precipitation,relative_humidity_2m,weather_code',
            'timezone': 'America/Lima'}
        if modelo == 'era5':
            parametros['models'] = modelo
        datos = obtener_json(url, parametros)
        try:
            if datos['utc_offset_seconds'] != -18000:
                raise ValueError()
            horas = datos['hourly']['time']
            variables = [datos['hourly'][nombre] for nombre in ('temperature_2m', 'precipitation', 'relative_humidity_2m', 'weather_code')]
            if not horas or len(horas) > 744 or any(len(v) != len(horas) for v in variables):
                raise ValueError()
            vistas = set()
            for i, valor in enumerate(horas):
                hora = datetime.fromisoformat(valor)
                if hora.tzinfo or hora.minute or hora.second or hora.microsecond or not inicio <= hora.date() <= fin or hora in vistas:
                    raise ValueError()
                vistas.add(hora)
                valores = [v[i] for v in variables]
                if any(v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)) for v in valores):
                    raise ValueError()
                temperatura, lluvia, humedad, codigo = valores
                if ((temperatura is not None and not -100 <= temperatura <= 70) or
                    (lluvia is not None and not 0 <= lluvia <= 1000) or
                    (humedad is not None and not 0 <= humedad <= 100) or
                    (codigo is not None and (not isinstance(codigo, int) or not 0 <= codigo <= 99))):
                    raise ValueError()
                if hora > ahora:
                    continue
                filas.append(dict(hora=hora, temperatura_c=temperatura, precipitacion_mm=lluvia,
                    humedad_porcentaje=humedad, codigo_tiempo=codigo, tipo_dato=tipo, modelo=modelo,
                    latitud_modelo=datos.get('latitude'), longitud_modelo=datos.get('longitude')))
        except (KeyError, TypeError, ValueError, IndexError):
            raise ErrorProveedor('Open-Meteo devolvió datos horarios inconsistentes') from None
    if not filas:
        raise ErrorProveedor('No se recibieron datos climáticos para el rango')
    return filas
