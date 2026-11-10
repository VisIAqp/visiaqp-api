from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier

from sqlalchemy import select

from app.models import Procesamiento, ResultadoDeteccion
from tests.test_motor import _payload_proc, _payload_resultado


def crear_stream(client, headers, ids):
    return client.post('/api/procesamientos', headers=headers,
                       json=_payload_proc(ids, tipo_fuente='stream', ruta_archivo=None))


def en_paralelo(funcion):
    barrera = Barrier(2)
    def ejecutar():
        barrera.wait(timeout=5)
        return funcion()
    with ThreadPoolExecutor(max_workers=2) as grupo:
        return list(grupo.map(lambda _: ejecutar(), range(2)))


def test_reserva_stream_es_exclusiva_incluso_con_solicitudes_simultaneas(client, motor_headers, datos_base, abrir_sesion):
    respuestas = en_paralelo(lambda: crear_stream(client, motor_headers, datos_base))
    assert sorted(r.status_code for r in respuestas) == [201, 409]
    with abrir_sesion() as db:
        activos = db.scalars(select(Procesamiento).where(Procesamiento.estado == 'procesando')).all()
        assert len(activos) == 1


def test_camara_vencida_puede_ser_reservada_y_motor_antiguo_no_revive(client, motor_headers, datos_base, abrir_sesion):
    id_antiguo = crear_stream(client, motor_headers, datos_base).json()['id_procesamiento']
    with abrir_sesion() as db:
        db.get(Procesamiento, id_antiguo).ultima_actividad = datetime.now() - timedelta(minutes=3)
        db.commit()
    nueva = crear_stream(client, motor_headers, datos_base)
    assert nueva.status_code == 201
    assert nueva.json()['id_procesamiento'] != id_antiguo
    actividad = client.patch(f'/api/procesamientos/{id_antiguo}/actividad', json={}, headers=motor_headers)
    assert actividad.status_code == 409
    resultado = client.post(f'/api/procesamientos/{id_antiguo}/resultados', headers=motor_headers,
                            json=_payload_resultado(datos_base))
    assert resultado.status_code == 409
    client.patch(f'/api/procesamientos/{id_antiguo}', headers=motor_headers, json={'estado': 'completado'})
    with abrir_sesion() as db:
        assert db.get(Procesamiento, id_antiguo).estado == 'error'


def test_actividad_actualiza_mediciones_y_exige_api_key(client, motor_headers, datos_base, abrir_sesion):
    id_proc = crear_stream(client, motor_headers, datos_base).json()['id_procesamiento']
    ruta = f'/api/procesamientos/{id_proc}/actividad'
    assert client.patch(ruta, json={}).status_code == 401
    assert client.patch(ruta, json={'fps_procesamiento': -1}, headers=motor_headers).status_code == 422
    assert client.patch(ruta, json={'fps_procesamiento': 4.5, 'retraso_seg': 0.2,
                                   'ultima_muestra': '2026-10-31T10:00:00'}, headers=motor_headers).status_code == 200
    with abrir_sesion() as db:
        proc = db.get(Procesamiento, id_proc)
        assert float(proc.fps_procesamiento) == 4.5
        assert float(proc.retraso_seg) == 0.2
        assert proc.ultima_muestra == datetime(2026, 10, 31, 10)


def test_reenvio_concurrente_de_ventana_no_duplica_resultados(client, motor_headers, datos_base, abrir_sesion):
    id_proc = crear_stream(client, motor_headers, datos_base).json()['id_procesamiento']
    payload = {**_payload_resultado(datos_base), 'clave_ventana': 'ventana-1'}
    ruta = f'/api/procesamientos/{id_proc}/resultados'
    respuestas = en_paralelo(lambda: client.post(ruta, headers=motor_headers, json=payload))
    assert [r.status_code for r in respuestas] == [201, 201]
    assert respuestas[0].json()['id_resultado'] == respuestas[1].json()['id_resultado']
    with abrir_sesion() as db:
        assert len(db.scalars(select(ResultadoDeteccion)).all()) == 1
    assert client.post(ruta, headers=motor_headers, json={**payload, 'cantidad_peatones': 40}).status_code == 409


def test_listado_cierra_video_abandonado_sin_reencolarlo_ni_borrar_resultados(client, motor_headers, datos_base, abrir_sesion, usuarios):
    respuesta = client.post('/api/procesamientos', headers=motor_headers, json=_payload_proc(datos_base))
    id_proc = respuesta.json()['id_procesamiento']
    with abrir_sesion() as db:
        db.get(Procesamiento, id_proc).ultima_actividad = datetime.now() - timedelta(minutes=3)
        db.commit()
    filas = client.get('/api/procesamientos', headers=usuarios['ana']['headers']).json()
    assert next(p for p in filas if p['id_procesamiento'] == id_proc)['estado'] == 'error'
    assert client.patch(f'/api/procesamientos/{id_proc}/iniciar', headers=motor_headers).status_code == 409
