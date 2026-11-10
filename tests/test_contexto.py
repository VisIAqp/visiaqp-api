from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Zona, Procesamiento, ResultadoDeteccion
from app.models.contexto import ClimaHora, EventoCalendario, SincronizacionContexto
from app.services import contexto_proveedores as proveedores


def pedir(client, usuarios, ruta, rol='ana', metodo='get', **kwargs):
    return getattr(client, metodo)('/api/contexto/' + ruta, headers=usuarios[rol]['headers'], **kwargs)


@pytest.fixture
def zona_geo(datos_base, abrir_sesion):
    with abrir_sesion() as db:
        z = db.get(Zona, datos_base['id_zona'])
        z.latitud, z.longitud = Decimal('-16.3989000'), Decimal('-71.5350000')
        db.commit()
    return datos_base['id_zona']


def clima_de_prueba(**cambios):
    return dict(hora=datetime(2026, 10, 1, 10), temperatura_c=20, precipitacion_mm=0,
        humedad_porcentaje=40, codigo_tiempo=0, tipo_dato='historico_modelado',
        modelo='era5', latitud_modelo=-16.4, longitud_modelo=-71.5, **cambios)


@pytest.mark.parametrize('ruta', ['calendario?anio=2026', 'clima?id_zona=1&desde=2026-10-01&hasta=2026-10-01', 'series'])
def test_contexto_requiere_sesion(client, ruta):
    assert client.get('/api/contexto/' + ruta).status_code == 401


def test_solo_admin_sincroniza_y_crea_eventos(client, usuarios, zona_geo):
    assert pedir(client, usuarios, 'calendario/sincronizar?anio=2026', metodo='post').status_code == 403
    assert pedir(client, usuarios, 'clima/sincronizar', metodo='post', json={
        'id_zona': zona_geo, 'desde': '2026-10-01', 'hasta': '2026-10-01'}).status_code == 403
    assert pedir(client, usuarios, 'eventos', metodo='post', json={}).status_code == 403


def test_calendario_sincroniza_sin_duplicar_y_lectura_no_llama_proveedor(client, usuarios, monkeypatch, abrir_sesion):
    llamadas = []
    def feriados(anio):
        llamadas.append(anio)
        return [{'fecha': date(2026, 1, 1), 'nombre': 'Año Nuevo'}]
    monkeypatch.setattr(proveedores, 'feriados_peru', feriados)
    for _ in range(2):
        assert pedir(client, usuarios, 'calendario/sincronizar?anio=2026', rol='admin', metodo='post').status_code == 200
    assert llamadas == [2026]
    respuesta = pedir(client, usuarios, 'calendario', params={'anio': 2026})
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()['total'] == 1
    assert respuesta.json()['datos'][0]['editable'] is False
    assert llamadas == [2026]
    with abrir_sesion() as db:
        assert len(db.scalars(select(EventoCalendario)).all()) == 1


def test_fallo_externo_no_borra_calendario_y_aplica_espera(client, usuarios, monkeypatch, abrir_sesion):
    monkeypatch.setattr(proveedores, 'feriados_peru', lambda _: [{'fecha': date(2026, 1, 1), 'nombre': 'Año Nuevo'}])
    pedir(client, usuarios, 'calendario/sincronizar?anio=2026', rol='admin', metodo='post')
    with abrir_sesion() as db:
        sync = db.get(SincronizacionContexto, 'calendario:PE:2026')
        sync.ultimo_exito = sync.ultimo_intento = datetime.now() - timedelta(days=2)
        db.commit()
    def fallar(_):
        raise proveedores.ErrorProveedor('Proveedor no disponible')
    monkeypatch.setattr(proveedores, 'feriados_peru', fallar)
    assert pedir(client, usuarios, 'calendario/sincronizar?anio=2026', rol='admin', metodo='post').status_code == 503
    assert pedir(client, usuarios, 'calendario', params={'anio': 2026}).json()['total'] == 1
    assert pedir(client, usuarios, 'calendario/sincronizar?anio=2026', rol='admin', metodo='post').status_code == 429


def test_evento_local_requiere_zona_y_fuente_y_no_se_aplica_a_otra(client, usuarios, datos_base):
    payload = {'fecha': '2026-08-15', 'nombre': 'Evento local de prueba', 'tipo': 'evento',
               'alcance': 'local', 'referencia': 'https://www.gob.pe/ejemplo'}
    assert pedir(client, usuarios, 'eventos', rol='admin', metodo='post', json=payload).status_code == 422
    payload['id_zona'] = datos_base['id_zona']
    respuesta = pedir(client, usuarios, 'eventos', rol='admin', metodo='post', json=payload)
    assert respuesta.status_code == 201, respuesta.text
    evento = respuesta.json()
    assert evento['editable'] is True
    assert pedir(client, usuarios, 'calendario', params={'anio': 2026}).json()['total'] == 0
    assert pedir(client, usuarios, 'calendario', params={'anio': 2026, 'id_zona': datos_base['id_zona']}).json()['total'] == 1
    payload['activo'] = False
    assert pedir(client, usuarios, 'eventos/' + str(evento['id_evento']), rol='admin', metodo='put', json=payload).status_code == 200
    assert pedir(client, usuarios, 'calendario', params={'anio': 2026, 'id_zona': datos_base['id_zona']}).json()['total'] == 0


def test_clima_requiere_coordenadas_y_guarda_cero_sin_confundir_null(client, usuarios, zona_geo, monkeypatch, datos_base):
    llamadas = []
    def clima(*args):
        llamadas.append(args)
        return [clima_de_prueba()]
    monkeypatch.setattr(proveedores, 'clima_por_rango', clima)
    payload = {'id_zona': zona_geo, 'desde': '2026-10-01', 'hasta': '2026-10-01'}
    r = pedir(client, usuarios, 'clima/sincronizar', rol='admin', metodo='post', json=payload)
    assert r.status_code == 200, r.text
    assert pedir(client, usuarios, 'clima/sincronizar', rol='admin', metodo='post', json=payload).json()['estado'] == 'cache'
    assert len(llamadas) == 1
    r = pedir(client, usuarios, 'clima', params=payload)
    assert r.status_code == 200, r.text
    assert r.json()['datos'][0]['precipitacion_mm'] == 0
    assert r.json()['datos'][0]['tipo_dato'] == 'historico_modelado'
    assert len(llamadas) == 1
    payload['id_zona'] = datos_base['id_zona'] + 1
    assert pedir(client, usuarios, 'clima/sincronizar', rol='admin', metodo='post', json=payload).status_code == 422


def test_cambio_de_coordenadas_no_reutiliza_clima_de_otra_ubicacion(client, usuarios, zona_geo, monkeypatch, abrir_sesion):
    monkeypatch.setattr(proveedores, 'clima_por_rango', lambda *a: [clima_de_prueba()])
    payload = {'id_zona': zona_geo, 'desde': '2026-10-01', 'hasta': '2026-10-01'}
    pedir(client, usuarios, 'clima/sincronizar', rol='admin', metodo='post', json=payload)
    with abrir_sesion() as db:
        db.get(Zona, zona_geo).latitud = Decimal('-16.5000000')
        db.commit()
    assert pedir(client, usuarios, 'clima', params=payload).json()['total'] == 0


def test_series_cruzan_hora_de_captura_sin_multiplicar_por_eventos(client, usuarios, zona_geo, datos_base, abrir_sesion):
    with abrir_sesion() as db:
        p = Procesamiento(id_zona=zona_geo, id_camara=datos_base['id_camara'], tipo_fuente='video',
            estado='completado', fecha_captura_inicio=datetime(2026, 10, 1, 10))
        db.add(p)
        db.flush()
        db.add(ResultadoDeteccion(id_procesamiento=p.id_procesamiento,
            periodo_inicio=datetime(2026, 10, 1, 10, 5), periodo_fin=datetime(2026, 10, 1, 10, 6),
            cantidad_peatones=5, promedio_presentes=0, max_presentes=0, segundos_observados=60))
        db.add(ClimaHora(**clima_de_prueba(), id_zona=zona_geo, latitud=-16.3989, longitud=-71.535))
        for nombre in ('Feriado de prueba', 'Segundo feriado de prueba'):
            db.add(EventoCalendario(fecha=date(2026, 10, 1), nombre=nombre, tipo='feriado', alcance='nacional', referencia='https://www.gob.pe/ejemplo'))
        db.commit()
    r = pedir(client, usuarios, 'series', params={'id_zona': zona_geo,
        'desde': '2026-10-01T00:00:00', 'hasta': '2026-10-02T00:00:00'})
    assert r.status_code == 200, r.text
    assert r.json()['total'] == 1
    fila = r.json()['datos'][0]
    assert fila['promedio_presentes'] == 0
    assert fila['temperatura_c'] == 20
    assert fila['es_feriado'] is True
    assert fila['es_no_laborable'] is False


def test_proveedor_nager_no_convierte_regional_en_nacional(monkeypatch):
    base = dict(date='2026-01-01', localName='Feriado', countryCode='PE', types=['Public'])
    monkeypatch.setattr(proveedores, 'obtener_json', lambda *a: [{**base, 'global': True}, {**base, 'global': False}])
    assert len(proveedores.feriados_peru(2026)) == 1


@pytest.mark.parametrize('valor', [float('nan'), -1, 1001])
def test_proveedor_clima_rechaza_lluvia_invalida(monkeypatch, valor):
    monkeypatch.setattr(proveedores, 'obtener_json', lambda *a: {'utc_offset_seconds': -18000,
        'hourly': {'time': ['2026-10-01T10:00'], 'temperature_2m': [20], 'precipitation': [valor],
                   'relative_humidity_2m': [40], 'weather_code': [0]}})
    with pytest.raises(proveedores.ErrorProveedor):
        proveedores.clima_por_rango(-16, -71, date(2026, 10, 1), date(2026, 10, 1), datetime(2026, 10, 31))


def test_proveedor_clima_separa_modelo_reciente_y_descarta_horas_futuras(monkeypatch):
    llamadas = []
    def obtener(url, params):
        llamadas.append(url)
        fecha = params['start_date']
        return {'utc_offset_seconds': -18000, 'hourly': {'time': [fecha + 'T10:00', fecha + 'T23:00'],
            'temperature_2m': [None, 20], 'precipitation': [None, 0],
            'relative_humidity_2m': [None, 40], 'weather_code': [None, 0]}}
    monkeypatch.setattr(proveedores, 'obtener_json', obtener)
    filas = proveedores.clima_por_rango(-16, -71, date(2026, 10, 20), date(2026, 10, 31), datetime(2026, 10, 31, 12))
    assert len(llamadas) == 2
    assert {f['tipo_dato'] for f in filas} == {'historico_modelado', 'estimacion_reciente'}
    assert any(f['temperatura_c'] is None for f in filas)
    assert all(f['hora'] <= datetime(2026, 10, 31, 12) for f in filas)


def test_clima_no_admite_rangos_futuros_y_series_requiere_zona(client, usuarios, zona_geo):
    r = pedir(client, usuarios, 'clima/sincronizar', rol='admin', metodo='post', json={
        'id_zona': zona_geo, 'desde': '2099-01-01', 'hasta': '2099-01-02'})
    assert r.status_code == 422
    assert pedir(client, usuarios, 'series').status_code == 422
