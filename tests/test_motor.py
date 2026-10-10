from datetime import datetime
from decimal import Decimal

from app.models import Procesamiento, ResultadoDeteccion


def _payload_proc(ids, **cambios):
    base = {
        "id_zona": ids["id_zona"],
        "id_camara": ids["id_camara"],
        "tipo_fuente": "video",
        "ruta_archivo": "data/videos/demo.mp4",
        "fecha_captura_inicio": "2026-09-20T14:30:00",
    }
    return {**base, **cambios}


def _payload_resultado(ids, **cambios):
    base = {
        "id_zona": ids["id_zona"],
        "id_camara": ids["id_camara"],
        "periodo_inicio": "2026-09-20T14:30:00.200000",
        "periodo_fin": "2026-09-20T14:30:10.200000",
        "cantidad_peatones": 39,
        "confianza_promedio": 0.62,
    }
    return {**base, **cambios}


def _crear_proc(client, headers, ids, **cambios) -> int:
    r = client.post("/api/procesamientos", json=_payload_proc(ids, **cambios), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id_procesamiento"]


# ---------- API key ----------

def test_sin_api_key_da_401(client, datos_base):
    assert client.get("/api/camaras").status_code == 401


def test_api_key_incorrecta_da_401(client, datos_base):
    r = client.get("/api/camaras", headers={"X-API-Key": "incorrecta"})
    assert r.status_code == 401


# ---------- GET /api/camaras ----------

def test_listar_camaras_solo_activas_con_url_y_poligono(client, motor_headers, datos_base):
    r = client.get("/api/camaras", headers=motor_headers)
    assert r.status_code == 200
    camaras = r.json()
    nombres = {c["nombre"] for c in camaras}
    assert "Cam inactiva" not in nombres
    assert "Cam activa" in nombres

    cam = next(c for c in camaras if c["nombre"] == "Cam activa")
    assert cam["url_stream"] == "rtsp://user:pass@host/stream"
    assert cam["zone_polygon"][0] == [0.05, 0.1]
    assert {"id_camara", "id_zona", "estado"} <= cam.keys()


# ---------- POST /api/procesamientos ----------

def test_crear_procesamiento(client, motor_headers, datos_base, abrir_sesion):
    id_proc = _crear_proc(client, motor_headers, datos_base)
    with abrir_sesion() as db:
        proc = db.get(Procesamiento, id_proc)
        assert proc.estado == "procesando"
        assert proc.tipo_fuente == "video"
        assert proc.fecha_captura_inicio == datetime(2026, 9, 20, 14, 30, 0)


def test_crear_procesamiento_stream_sin_ruta(client, motor_headers, datos_base):
    r = client.post(
        "/api/procesamientos",
        json=_payload_proc(datos_base, tipo_fuente="stream", ruta_archivo=None),
        headers=motor_headers,
    )
    assert r.status_code == 201


def test_crear_procesamiento_camara_de_otra_zona_da_422(client, motor_headers, datos_base):
    r = client.post(
        "/api/procesamientos",
        json=_payload_proc(datos_base, id_camara=datos_base["id_camara_otra_zona"]),
        headers=motor_headers,
    )
    assert r.status_code == 422


def test_crear_procesamiento_tipo_fuente_invalido_da_422(client, motor_headers, datos_base):
    r = client.post(
        "/api/procesamientos",
        json=_payload_proc(datos_base, tipo_fuente="otro"),
        headers=motor_headers,
    )
    assert r.status_code == 422


# ---------- POST /api/procesamientos/{id}/resultados ----------

def test_registrar_resultado_convierte_confianza_a_porcentaje(
    client, motor_headers, datos_base, abrir_sesion
):
    id_proc = _crear_proc(client, motor_headers, datos_base)
    r = client.post(
        f"/api/procesamientos/{id_proc}/resultados",
        json=_payload_resultado(datos_base),
        headers=motor_headers,
    )
    assert r.status_code == 201
    id_resultado = r.json()["id_resultado"]

    with abrir_sesion() as db:
        res = db.get(ResultadoDeteccion, id_resultado)
        assert res.id_procesamiento == id_proc
        assert res.cantidad_peatones == 39
        assert res.confianza_promedio == Decimal("62.00")


def test_resultado_sin_confianza_es_valido(client, motor_headers, datos_base):
    id_proc = _crear_proc(client, motor_headers, datos_base)
    r = client.post(
        f"/api/procesamientos/{id_proc}/resultados",
        json=_payload_resultado(datos_base, confianza_promedio=None),
        headers=motor_headers,
    )
    assert r.status_code == 201


def test_resultado_en_procesamiento_inexistente_da_404(client, motor_headers, datos_base):
    r = client.post(
        "/api/procesamientos/99999/resultados",
        json=_payload_resultado(datos_base),
        headers=motor_headers,
    )
    assert r.status_code == 404


def test_resultado_en_procesamiento_cerrado_da_409(client, motor_headers, datos_base):
    id_proc = _crear_proc(client, motor_headers, datos_base)
    client.patch(
        f"/api/procesamientos/{id_proc}",
        json={"estado": "completado", "fecha_fin_proceso": datetime.now().isoformat()},
        headers=motor_headers,
    )
    r = client.post(
        f"/api/procesamientos/{id_proc}/resultados",
        json=_payload_resultado(datos_base),
        headers=motor_headers,
    )
    assert r.status_code == 409


def test_resultado_con_zona_distinta_da_422(client, motor_headers, datos_base):
    id_proc = _crear_proc(client, motor_headers, datos_base)
    r = client.post(
        f"/api/procesamientos/{id_proc}/resultados",
        json=_payload_resultado(datos_base, id_zona=datos_base["id_zona"] + 999),
        headers=motor_headers,
    )
    assert r.status_code == 422


def test_resultado_con_datos_invalidos_da_422(client, motor_headers, datos_base):
    id_proc = _crear_proc(client, motor_headers, datos_base)
    url = f"/api/procesamientos/{id_proc}/resultados"

    negativo = _payload_resultado(datos_base, cantidad_peatones=-1)
    assert client.post(url, json=negativo, headers=motor_headers).status_code == 422

    confianza_alta = _payload_resultado(datos_base, confianza_promedio=1.5)
    assert client.post(url, json=confianza_alta, headers=motor_headers).status_code == 422

    periodo_invertido = _payload_resultado(
        datos_base,
        periodo_inicio="2026-09-20T14:31:00",
        periodo_fin="2026-09-20T14:30:00",
    )
    assert client.post(url, json=periodo_invertido, headers=motor_headers).status_code == 422


# ---------- PATCH /api/procesamientos/{id} ----------

def test_cerrar_completado(client, motor_headers, datos_base, abrir_sesion):
    id_proc = _crear_proc(client, motor_headers, datos_base)
    r = client.patch(
        f"/api/procesamientos/{id_proc}",
        json={
            "estado": "completado",
            "fecha_fin_proceso": datetime.now().isoformat(),
            "mensaje_error": None,
        },
        headers=motor_headers,
    )
    assert r.status_code == 200
    assert r.json() == {"id_procesamiento": id_proc, "estado": "completado"}

    with abrir_sesion() as db:
        proc = db.get(Procesamiento, id_proc)
        assert proc.estado == "completado"
        assert proc.fecha_fin_proceso is not None


def test_cerrar_con_error_guarda_mensaje(client, motor_headers, datos_base, abrir_sesion):
    id_proc = _crear_proc(client, motor_headers, datos_base)
    client.patch(
        f"/api/procesamientos/{id_proc}",
        json={"estado": "error", "mensaje_error": "No se pudo abrir la fuente"},
        headers=motor_headers,
    )
    with abrir_sesion() as db:
        proc = db.get(Procesamiento, id_proc)
        assert proc.estado == "error"
        assert proc.mensaje_error == "No se pudo abrir la fuente"


def test_cerrar_con_fecha_anterior_al_inicio_se_ajusta(
    client, motor_headers, datos_base, abrir_sesion
):
    """Reloj del motor atrasado respecto a la BD: no debe violar fecha_fin >= fecha_inicio."""
    id_proc = _crear_proc(client, motor_headers, datos_base)
    r = client.patch(
        f"/api/procesamientos/{id_proc}",
        json={"estado": "completado", "fecha_fin_proceso": "2020-01-01T00:00:00"},
        headers=motor_headers,
    )
    assert r.status_code == 200
    with abrir_sesion() as db:
        proc = db.get(Procesamiento, id_proc)
        assert proc.fecha_fin_proceso >= proc.fecha_inicio_proceso


def test_cerrar_inexistente_da_404(client, motor_headers, datos_base):
    r = client.patch(
        "/api/procesamientos/99999", json={"estado": "completado"}, headers=motor_headers
    )
    assert r.status_code == 404


def test_cerrar_con_estado_invalido_da_422(client, motor_headers, datos_base):
    id_proc = _crear_proc(client, motor_headers, datos_base)
    r = client.patch(
        f"/api/procesamientos/{id_proc}", json={"estado": "procesando"}, headers=motor_headers
    )
    assert r.status_code == 422


# ---------- Ciclo completo, tal como lo hace visiaqp-ai ----------

def test_ciclo_completo_del_motor(client, motor_headers, datos_base):
    assert client.get("/api/camaras", headers=motor_headers).status_code == 200
    id_proc = _crear_proc(client, motor_headers, datos_base)
    for i in range(3):
        r = client.post(
            f"/api/procesamientos/{id_proc}/resultados",
            json=_payload_resultado(
                datos_base,
                periodo_inicio=f"2026-09-20T14:3{i}:00",
                periodo_fin=f"2026-09-20T14:3{i}:10",
                cantidad_peatones=10 + i,
            ),
            headers=motor_headers,
        )
        assert r.status_code == 201
    r = client.patch(
        f"/api/procesamientos/{id_proc}",
        json={"estado": "completado", "fecha_fin_proceso": datetime.now().isoformat()},
        headers=motor_headers,
    )
    assert r.status_code == 200