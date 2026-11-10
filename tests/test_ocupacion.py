from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Camara, Indicador
from tests.test_indicadores import id_proc  # noqa: F401


def enviar(client, headers, ids, proc, minuto=0, promedio=4, maximo=8, segundos=10, **extras):
    payload = {
        "id_zona": ids["id_zona"], "id_camara": ids["id_camara"],
        "periodo_inicio": f"2026-09-20T14:{minuto:02d}:00",
        "periodo_fin": f"2026-09-20T14:{minuto:02d}:{segundos:02d}",
        "cantidad_peatones": 20, "promedio_presentes": promedio,
        "max_presentes": maximo, "segundos_observados": segundos,
    }
    return client.post(f"/api/procesamientos/{proc}/resultados", json={**payload, **extras}, headers=headers)


def hora(abrir_sesion):
    with abrir_sesion() as db:
        return db.scalars(select(Indicador).where(Indicador.periodo_tipo == "hora")).one()


def test_ocupacion_ponderada_y_nivel_separados_de_ids(client, motor_headers, datos_base, id_proc, abrir_sesion):
    assert enviar(client, motor_headers, datos_base, id_proc).status_code == 201
    assert enviar(client, motor_headers, datos_base, id_proc, minuto=1, promedio=16, maximo=20, segundos=50).status_code == 201
    ind = hora(abrir_sesion)
    assert ind.total_peatones == 40
    assert ind.promedio_presentes == Decimal("14.0000")
    assert ind.max_presentes == 20
    assert ind.segundos_observados == 60
    assert ind.nivel_ocupacion == "medio"
    assert ind.estado_ocupacion == "disponible"


def test_no_convierte_ids_historicos_en_ocupacion(client, motor_headers, datos_base, id_proc, abrir_sesion):
    assert enviar(client, motor_headers, datos_base, id_proc, promedio=None, maximo=None,
                  segundos_observados=None).status_code == 201
    ind = hora(abrir_sesion)
    assert ind.promedio_presentes is None
    assert ind.nivel_ocupacion is None
    assert ind.estado_ocupacion == "sin_datos"


def test_mezcla_de_historicos_y_mediciones_no_presenta_ocupacion_completa(client, motor_headers, datos_base, id_proc, abrir_sesion):
    assert enviar(client, motor_headers, datos_base, id_proc).status_code == 201
    assert enviar(client, motor_headers, datos_base, id_proc, minuto=1, promedio=None, maximo=None,
                  segundos_observados=None).status_code == 201
    assert hora(abrir_sesion).estado_ocupacion == "datos_incompletos"
    assert hora(abrir_sesion).promedio_presentes is None


def test_dos_camaras_no_se_suman_sin_politica_espacial(client, motor_headers, datos_base, id_proc, abrir_sesion):
    assert enviar(client, motor_headers, datos_base, id_proc).status_code == 201
    with abrir_sesion() as db:
        cam = Camara(id_zona=datos_base["id_zona"], nombre="Segunda vista", url_stream="rtsp://ejemplo/segunda")
        db.add(cam)
        db.commit()
        cam_id = cam.id_camara
    respuesta = client.post("/api/procesamientos", headers=motor_headers, json={
        "id_zona": datos_base["id_zona"], "id_camara": cam_id, "tipo_fuente": "video",
        "ruta_archivo": "segunda.mp4", "fecha_captura_inicio": "2026-09-20T14:00:00",
    })
    assert respuesta.status_code == 201
    ids = {**datos_base, "id_camara": cam_id}
    assert enviar(client, motor_headers, ids, respuesta.json()["id_procesamiento"]).status_code == 201
    assert hora(abrir_sesion).estado_ocupacion == "fuentes_sin_consolidar"
    assert hora(abrir_sesion).promedio_presentes is None


@pytest.mark.parametrize("extras", [
    {"max_presentes": None}, {"promedio_presentes": 9},
    {"max_presentes": 21}, {"segundos_observados": 11},
    {"segundos_observados": 0}, {"promedio_presentes": -1},
])
def test_rechaza_ocupacion_inconsistente(client, motor_headers, datos_base, id_proc, extras):
    assert enviar(client, motor_headers, datos_base, id_proc, **extras).status_code == 422


def test_cero_personas_es_medicion_valida(client, motor_headers, datos_base, id_proc, abrir_sesion):
    assert enviar(client, motor_headers, datos_base, id_proc, promedio=0, maximo=0,
                  cantidad_peatones=0).status_code == 201
    ind = hora(abrir_sesion)
    assert ind.promedio_presentes == 0
    assert ind.nivel_ocupacion == "bajo"
    assert ind.estado_ocupacion == "disponible"


def test_api_expone_ocupacion_y_conserva_contrato_anterior(client, motor_headers, datos_base, id_proc, usuarios):
    assert enviar(client, motor_headers, datos_base, id_proc).status_code == 201
    respuesta = client.get("/api/indicadores", params={"id_zona": datos_base["id_zona"]},
                           headers=usuarios["ana"]["headers"])
    assert respuesta.status_code == 200
    fila = respuesta.json()[0]
    assert fila["total_peatones"] == 20
    assert fila["promedio_presentes"] == 4
    assert fila["max_presentes"] == 8
    assert fila["segundos_observados"] == 10
    assert fila["nivel_ocupacion"] == "bajo"
    assert fila["estado_ocupacion"] == "disponible"
