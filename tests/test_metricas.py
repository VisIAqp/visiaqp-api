from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import Procesamiento, ResultadoDeteccion


RANGO = {'desde': '2026-10-31T00:00:00', 'hasta': '2026-11-01T00:00:00'}


@pytest.fixture
def mediciones(datos_base, abrir_sesion):
    with abrir_sesion() as db:
        def proceso(camara, zona):
            p = Procesamiento(id_zona=zona, id_camara=camara, tipo_fuente='video',
                fecha_captura_inicio=datetime(2026, 10, 31, 10), estado='completado')
            db.add(p)
            db.flush()
            return p
        p = proceso(datos_base['id_camara'], datos_base['id_zona'])
        otra_camara = datos_base['id_camara_otra_zona']
        from app.models import Camara
        otra_zona = db.get(Camara, otra_camara).id_zona
        otro = proceso(otra_camara, otra_zona)
        db.add_all([
            ResultadoDeteccion(id_procesamiento=p.id_procesamiento,
                periodo_inicio=datetime(2026, 10, 31, 10), periodo_fin=datetime(2026, 10, 31, 10, 1),
                cantidad_peatones=35, promedio_presentes=10, max_presentes=25, segundos_observados=60),
            ResultadoDeteccion(id_procesamiento=p.id_procesamiento,
                periodo_inicio=datetime(2026, 10, 31, 10, 1), periodo_fin=datetime(2026, 10, 31, 10, 3),
                cantidad_peatones=35, promedio_presentes=20, max_presentes=25, segundos_observados=120),
            ResultadoDeteccion(id_procesamiento=otro.id_procesamiento,
                periodo_inicio=datetime(2026, 10, 31, 11), periodo_fin=datetime(2026, 10, 31, 11, 1),
                cantidad_peatones=7),
        ])
        db.commit()
        return {'id_procesamiento': p.id_procesamiento, 'otra_zona': otra_zona}


def consultar(client, usuarios, ruta, **filtros):
    return client.get('/api/metricas/' + ruta, headers=usuarios['ana']['headers'],
                      params={**RANGO, **filtros})


@pytest.mark.parametrize('ruta', ['resumen', 'series', 'comparativas', 'patrones',
                                 'distribucion-niveles', 'estado-camaras'])
def test_metricas_requieren_jwt(client, ruta):
    assert client.get('/api/metricas/' + ruta).status_code == 401


def test_serie_pondera_duracion_y_separa_legacy(client, usuarios, mediciones, datos_base):
    respuesta = consultar(client, usuarios, 'series')
    assert respuesta.status_code == 200, respuesta.text
    pagina = respuesta.json()
    assert pagina['total'] == 2
    fila = next(f for f in pagina['datos'] if f['id_zona'] == datos_base['id_zona'])
    assert fila['cantidad_ventanas'] == 2
    assert fila['suma_identificadores'] == 70
    assert fila['promedio_presentes'] == pytest.approx(16.6667)
    assert fila['max_presentes'] == 25
    assert fila['segundos_observados'] == 180
    assert fila['nivel_ocupacion'] == 'medio'
    assert fila['periodo_inicio'] == '2026-10-31T10:00:00'
    assert fila['periodo_fin'] == '2026-10-31T11:00:00'
    antigua = next(f for f in pagina['datos'] if f['id_zona'] == mediciones['otra_zona'])
    assert antigua['promedio_presentes'] is None
    assert antigua['nivel_ocupacion'] is None
    assert antigua['estado_ocupacion'] == 'sin_datos'


def test_paginacion_explicita_y_orden_estable(client, usuarios, mediciones):
    primera = consultar(client, usuarios, 'series', limite=1).json()
    segunda = consultar(client, usuarios, 'series', limite=1, desplazamiento=1).json()
    assert primera['total'] == segunda['total'] == 2
    assert primera['tiene_mas'] is True
    assert segunda['tiene_mas'] is False
    assert primera['datos'][0]['periodo_inicio'] < segunda['datos'][0]['periodo_inicio']


def test_rango_hasta_exclusivo_y_sin_rellenar_huecos(client, usuarios, mediciones, datos_base):
    respuesta = consultar(client, usuarios, 'series', id_zona=datos_base['id_zona'],
                          desde='2026-10-31T10:00:00', hasta='2026-10-31T10:01:00').json()
    assert respuesta['total'] == 1
    assert respuesta['datos'][0]['cantidad_ventanas'] == 1
    assert respuesta['datos'][0]['promedio_presentes'] == 10
    vacia = consultar(client, usuarios, 'series', desde='2026-10-31T12:00:00').json()
    assert vacia['total'] == 0
    assert vacia['datos'] == []


def test_periodo_diario_filtros_y_patrones(client, usuarios, mediciones, datos_base):
    serie = consultar(client, usuarios, 'series', periodo='dia',
                      id_procesamiento=mediciones['id_procesamiento']).json()
    assert serie['total'] == 1
    assert serie['datos'][0]['periodo_inicio'] == '2026-10-31T00:00:00'
    patron = consultar(client, usuarios, 'patrones', id_camara=datos_base['id_camara']).json()
    assert patron['datos'][0]['dia_semana'] == 5
    assert patron['datos'][0]['hora'] == 10
    assert patron['datos'][0]['promedio_presentes'] == pytest.approx(16.6667)
    assert consultar(client, usuarios, 'series', tipo_fuente='stream').json()['total'] == 0


def test_distribucion_no_clasifica_historico_como_bajo(client, usuarios, mediciones):
    respuesta = consultar(client, usuarios, 'distribucion-niveles')
    assert respuesta.status_code == 200, respuesta.text
    filas = respuesta.json()['datos']
    assert sum(f['cantidad_periodos'] for f in filas) == 2
    assert {f['nivel_ocupacion'] for f in filas} == {'medio', None}


def test_comparativa_no_mezcla_ejecuciones(client, usuarios, mediciones, datos_base, abrir_sesion):
    with abrir_sesion() as db:
        p = Procesamiento(id_zona=datos_base['id_zona'], id_camara=datos_base['id_camara'],
                          tipo_fuente='video', estado='completado', fecha_captura_inicio=datetime(2026, 10, 31, 10))
        db.add(p)
        db.flush()
        db.add(ResultadoDeteccion(id_procesamiento=p.id_procesamiento,
            periodo_inicio=datetime(2026, 10, 31, 10), periodo_fin=datetime(2026, 10, 31, 10, 1),
            cantidad_peatones=35, promedio_presentes=10, max_presentes=25, segundos_observados=60))
        db.commit()
    fila = consultar(client, usuarios, 'comparativas', id_zona=datos_base['id_zona']).json()['datos'][0]
    assert fila['procesamientos_distintos'] == 2
    assert fila['estado_ocupacion'] == 'ejecuciones_sin_consolidar'
    assert fila['promedio_presentes'] is None
    serie = consultar(client, usuarios, 'series', id_zona=datos_base['id_zona']).json()
    assert serie['total'] == 2
    assert all(f['estado_ocupacion'] == 'disponible' for f in serie['datos'])


def test_resumen_completo_no_limitado_a_500_ejecuciones(client, usuarios, mediciones, datos_base, abrir_sesion):
    with abrir_sesion() as db:
        db.add_all([Procesamiento(id_zona=datos_base['id_zona'], id_camara=datos_base['id_camara'],
            tipo_fuente='video', fecha_captura_inicio=datetime(2026, 10, 31), estado='pendiente') for _ in range(501)])
        db.commit()
    respuesta = consultar(client, usuarios, 'resumen')
    assert respuesta.status_code == 200, respuesta.text
    resumen = respuesta.json()
    assert resumen['cantidad_ventanas'] == 3
    assert resumen['suma_identificadores'] == 77
    assert resumen['ventanas_con_ocupacion'] == 2
    assert resumen['videos_pendientes'] == 501
    assert resumen['procesamientos_en_curso'] == 0
    assert resumen['camaras_registradas'] == 3
    assert resumen['camaras_habilitadas'] == 2


def test_estado_camaras_expira_ejecucion_y_no_expone_url(client, usuarios, datos_base, abrir_sesion):
    with abrir_sesion() as db:
        p = Procesamiento(id_zona=datos_base['id_zona'], id_camara=datos_base['id_camara'],
            tipo_fuente='stream', estado='procesando', fecha_captura_inicio=datetime.now(),
            ultima_actividad=datetime.now() - timedelta(minutes=3), fps_procesamiento=2)
        db.add(p)
        db.commit()
    respuesta = client.get('/api/metricas/estado-camaras', headers=usuarios['ana']['headers'])
    assert respuesta.status_code == 200, respuesta.text
    filas = respuesta.json()['datos']
    assert next(f for f in filas if f['id_camara'] == datos_base['id_camara'])['estado_operativo'] == 'interrumpida'
    assert 'url_stream' not in respuesta.text
    assert 'rtsp://' not in respuesta.text
    assert any(f['estado_operativo'] == 'deshabilitada' for f in filas)


@pytest.mark.parametrize('filtros', [
    {'hasta': '2026-10-30T00:00:00'},
    {'desde': '2026-09-01T00:00:00'},
    {'desde': '2026-10-31T00:00:00-05:00'},
    {'limite': 1001}, {'desplazamiento': -1}, {'periodo': 'mes'},
])
def test_rechaza_consultas_invalidas(client, usuarios, filtros):
    assert consultar(client, usuarios, 'series', **filtros).status_code == 422


def test_filtros_incompatibles_y_entidades_inexistentes(client, usuarios, mediciones, datos_base):
    assert consultar(client, usuarios, 'series', id_zona=999999).status_code == 404
    assert consultar(client, usuarios, 'series', id_camara=datos_base['id_camara_otra_zona'],
                     id_zona=datos_base['id_zona']).status_code == 422
    assert consultar(client, usuarios, 'series', id_procesamiento=mediciones['id_procesamiento'],
                     tipo_fuente='stream').status_code == 422


def test_resumen_sin_datos_no_inventa_ocupacion(client, usuarios):
    respuesta = consultar(client, usuarios, 'resumen')
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()['cantidad_ventanas'] == 0
    assert respuesta.json()['ultima_ventana_fin'] is None
    assert consultar(client, usuarios, 'comparativas').json()['datos'] == []


def test_ocupacion_cero_y_umbral_actual_de_zona(client, usuarios, mediciones, datos_base, abrir_sesion):
    from app.models import UmbralConcentracion
    with abrir_sesion() as db:
        umbral = db.scalars(select(UmbralConcentracion).where(UmbralConcentracion.id_zona == datos_base['id_zona'])).one()
        umbral.umbral_medio, umbral.umbral_alto = 50, 100
        db.add(ResultadoDeteccion(id_procesamiento=mediciones['id_procesamiento'],
            periodo_inicio=datetime(2026, 10, 31, 12), periodo_fin=datetime(2026, 10, 31, 12, 1),
            cantidad_peatones=0, promedio_presentes=0, max_presentes=0, segundos_observados=60))
        db.commit()
    filas = consultar(client, usuarios, 'series', id_zona=datos_base['id_zona']).json()['datos']
    assert filas[0]['nivel_ocupacion'] == 'bajo'
    assert filas[1]['promedio_presentes'] == 0
    assert filas[1]['max_presentes'] == 0
    assert filas[1]['estado_ocupacion'] == 'disponible'
    assert filas[1]['ultima_recepcion'] is not None
    assert isinstance(filas[1]['periodo_cerrado'], bool)


def test_varias_camaras_no_generan_total_de_ocupacion(client, usuarios, mediciones, datos_base, abrir_sesion):
    from app.models import Camara
    with abrir_sesion() as db:
        cam = Camara(id_zona=datos_base['id_zona'], nombre='Otra vista', url_stream='rtsp://prueba/otra')
        db.add(cam)
        db.flush()
        p = Procesamiento(id_zona=datos_base['id_zona'], id_camara=cam.id_camara,
                          tipo_fuente='video', estado='completado', fecha_captura_inicio=datetime(2026, 10, 31, 10))
        db.add(p)
        db.flush()
        db.add(ResultadoDeteccion(id_procesamiento=p.id_procesamiento,
            periodo_inicio=datetime(2026, 10, 31, 10), periodo_fin=datetime(2026, 10, 31, 10, 1),
            cantidad_peatones=20, promedio_presentes=15, max_presentes=20, segundos_observados=60))
        db.commit()
    fila = consultar(client, usuarios, 'comparativas', id_zona=datos_base['id_zona']).json()['datos'][0]
    assert fila['camaras_distintas'] == 2
    assert fila['estado_ocupacion'] == 'fuentes_sin_consolidar'
    assert fila['promedio_presentes'] is None


def test_estado_actual_no_confunde_video_reciente_con_transmision(client, usuarios, mediciones, datos_base, abrir_sesion):
    with abrir_sesion() as db:
        p = Procesamiento(id_zona=datos_base['id_zona'], id_camara=datos_base['id_camara'],
            tipo_fuente='stream', estado='procesando', fecha_captura_inicio=datetime.now(),
            ultima_actividad=datetime.now(), fps_procesamiento=2, retraso_seg=0)
        db.add(p)
        db.commit()
        id_stream = p.id_procesamiento
        db.add(Procesamiento(id_zona=datos_base['id_zona'], id_camara=datos_base['id_camara'],
            tipo_fuente='video', estado='completado', fecha_captura_inicio=datetime.now()))
        db.commit()
    respuesta = client.get('/api/metricas/estado-camaras', params={'id_camara': datos_base['id_camara'], 'limite': 1},
                           headers=usuarios['ana']['headers'])
    assert respuesta.status_code == 200, respuesta.text
    pagina = respuesta.json()
    assert pagina['total'] == 1
    assert pagina['datos'][0]['id_procesamiento'] == id_stream
    assert pagina['datos'][0]['estado_operativo'] == 'reportando'
    assert pagina['datos'][0]['edad_imagen_seg'] == 0
    assert consultar(client, usuarios, 'resumen', id_camara=datos_base['id_camara']).json()['transmisiones_reportando'] == 1


def test_fecha_fuera_de_rango_mysql_no_produce_error_interno(client, usuarios):
    respuesta = client.get('/api/metricas/series', params={'hasta': '0001-01-01T00:00:00'},
                           headers=usuarios['ana']['headers'])
    assert respuesta.status_code == 422
