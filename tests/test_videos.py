from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import Camara, Procesamiento, VideoDisponible


def _video(nombre, tamano=1000, fecha="2026-09-20T15:02:11"):
    return {"nombre_archivo": nombre, "tamano_bytes": tamano, "fecha_modificacion": fecha}


def _sync(client, headers, *videos):
    r = client.post("/api/videos/sincronizar", json={"videos": list(videos)}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _id_video(abrir_sesion, nombre):
    with abrir_sesion() as db:
        stmt = select(VideoDisponible).where(VideoDisponible.nombre_archivo == nombre)
        return db.scalars(stmt).one().id_video


def _solicitar(client, headers, id_video, id_camara, fecha="2026-09-20T14:30:00"):
    return client.post(
        "/api/procesamientos/solicitar",
        json={"id_video": id_video, "id_camara": id_camara, "fecha_captura_inicio": fecha},
        headers=headers,
    )


@pytest.fixture
def solicitud(client, motor_headers, datos_base, usuarios, abrir_sesion):
    """Una solicitud pendiente hecha por 'ana'."""
    _sync(client, motor_headers, _video("plaza/a.mp4"))
    id_video = _id_video(abrir_sesion, "plaza/a.mp4")
    r = _solicitar(client, usuarios["ana"]["headers"], id_video, datos_base["id_camara"])
    assert r.status_code == 201, r.text
    return {"id_procesamiento": r.json()["id_procesamiento"], "id_video": id_video}


# ---------- Sincronización (motor) ----------

def test_sincronizar_requiere_api_key(client):
    assert client.post("/api/videos/sincronizar", json={"videos": []}).status_code == 401


def test_sincronizar_registra_actualiza_y_marca_no_disponible(client, motor_headers):
    a, b = _video("a.mp4"), _video("b.mp4")

    assert _sync(client, motor_headers, a, b) == {
        "registrados": 2, "actualizados": 0, "no_disponibles": 0,
    }
    # b cambia de tamaño
    assert _sync(client, motor_headers, a, _video("b.mp4", tamano=2000)) == {
        "registrados": 0, "actualizados": 1, "no_disponibles": 0,
    }
    # b desaparece de la carpeta
    assert _sync(client, motor_headers, a) == {
        "registrados": 0, "actualizados": 0, "no_disponibles": 1,
    }
    # carpeta vacía: a desaparece
    assert _sync(client, motor_headers) == {
        "registrados": 0, "actualizados": 0, "no_disponibles": 1,
    }
    # vuelven ambos: se reactivan
    assert _sync(client, motor_headers, a, b) == {
        "registrados": 0, "actualizados": 2, "no_disponibles": 0,
    }


@pytest.mark.parametrize(
    "nombre", ["../x.mp4", "/etc/x.mp4", "a/../b.mp4", "C:/x.mp4", "a\\b.mp4", "a//b.mp4"]
)
def test_sincronizar_rechaza_nombres_inseguros(client, motor_headers, nombre):
    r = client.post(
        "/api/videos/sincronizar", json={"videos": [_video(nombre)]}, headers=motor_headers
    )
    assert r.status_code == 422


# ---------- Pendientes e inicio (motor) ----------

def test_pendientes_requiere_api_key(client):
    assert client.get("/api/procesamientos/pendientes").status_code == 401


def test_pendientes_incluye_poligono_y_no_url_stream(client, motor_headers, solicitud):
    r = client.get("/api/procesamientos/pendientes", headers=motor_headers)
    assert r.status_code == 200
    pendientes = r.json()
    assert len(pendientes) == 1

    p = pendientes[0]
    assert p["nombre_archivo"] == "plaza/a.mp4"
    assert p["nombre_camara"] == "Cam activa"
    assert p["zone_polygon"][0] == [0.05, 0.1]
    assert "url_stream" not in p
    assert "rtsp" not in r.text


def test_iniciar_reclama_una_sola_vez(client, motor_headers, solicitud, abrir_sesion):
    id_proc = solicitud["id_procesamiento"]
    url = f"/api/procesamientos/{id_proc}/iniciar"

    r = client.patch(url, headers=motor_headers)
    assert r.status_code == 200
    assert r.json() == {"id_procesamiento": id_proc, "estado": "procesando"}

    assert client.patch(url, headers=motor_headers).status_code == 409
    assert client.patch("/api/procesamientos/99999/iniciar", headers=motor_headers).status_code == 404
    assert client.get("/api/procesamientos/pendientes", headers=motor_headers).json() == []

    with abrir_sesion() as db:
        assert db.get(Procesamiento, id_proc).estado == "procesando"


# ---------- Solicitudes (frontend) ----------

def test_solicitud_guarda_usuario_y_queda_pendiente(
    client, datos_base, usuarios, solicitud, abrir_sesion
):
    with abrir_sesion() as db:
        proc = db.get(Procesamiento, solicitud["id_procesamiento"])
        assert proc.estado == "pendiente"
        assert proc.tipo_fuente == "video"
        assert proc.ruta_archivo == "plaza/a.mp4"
        assert proc.id_usuario == usuarios["ana"]["id"]
        assert proc.id_zona == datos_base["id_zona"]
        assert proc.fecha_captura_inicio == datetime(2026, 9, 20, 14, 30, 0)


def test_solicitar_requiere_token(client, datos_base):
    r = client.post(
        "/api/procesamientos/solicitar",
        json={"id_video": 1, "id_camara": datos_base["id_camara"],
              "fecha_captura_inicio": "2026-09-20T14:30:00"},
    )
    assert r.status_code == 401


def test_solicitar_video_inexistente_da_422(client, datos_base, usuarios):
    r = _solicitar(client, usuarios["ana"]["headers"], 9999, datos_base["id_camara"])
    assert r.status_code == 422


def test_solicitar_video_no_disponible_da_422(
    client, motor_headers, datos_base, usuarios, abrir_sesion
):
    _sync(client, motor_headers, _video("a.mp4"))
    id_video = _id_video(abrir_sesion, "a.mp4")
    _sync(client, motor_headers)  # desaparece
    r = _solicitar(client, usuarios["ana"]["headers"], id_video, datos_base["id_camara"])
    assert r.status_code == 422


def test_solicitar_con_camara_inactiva_da_422(
    client, motor_headers, datos_base, usuarios, abrir_sesion
):
    _sync(client, motor_headers, _video("a.mp4"))
    id_video = _id_video(abrir_sesion, "a.mp4")
    with abrir_sesion() as db:
        db.get(Camara, datos_base["id_camara"]).estado = "inactiva"
        db.commit()
    r = _solicitar(client, usuarios["ana"]["headers"], id_video, datos_base["id_camara"])
    assert r.status_code == 422


def test_solicitar_con_fecha_futura_da_422(
    client, motor_headers, datos_base, usuarios, abrir_sesion
):
    _sync(client, motor_headers, _video("a.mp4"))
    id_video = _id_video(abrir_sesion, "a.mp4")
    futura = (datetime.now() + timedelta(days=2)).isoformat()
    r = _solicitar(client, usuarios["ana"]["headers"], id_video, datos_base["id_camara"], futura)
    assert r.status_code == 422


def test_solicitud_duplicada_da_409(client, datos_base, usuarios, solicitud):
    r = _solicitar(
        client, usuarios["beto"]["headers"], solicitud["id_video"], datos_base["id_camara"]
    )
    assert r.status_code == 409


# ---------- Cancelar ----------

def test_no_se_puede_cancelar_solicitud_ajena(client, usuarios, solicitud):
    r = client.patch(
        f"/api/procesamientos/{solicitud['id_procesamiento']}/cancelar",
        headers=usuarios["beto"]["headers"],
    )
    assert r.status_code == 403


def test_cancelar_propia_y_el_motor_ya_no_puede_reclamarla(
    client, motor_headers, usuarios, solicitud, abrir_sesion
):
    id_proc = solicitud["id_procesamiento"]
    url = f"/api/procesamientos/{id_proc}/cancelar"

    r = client.patch(url, headers=usuarios["ana"]["headers"])
    assert r.status_code == 200
    assert r.json()["estado"] == "error"

    with abrir_sesion() as db:
        proc = db.get(Procesamiento, id_proc)
        assert proc.estado == "error"
        assert proc.mensaje_error == "Cancelado por el usuario"
        assert proc.fecha_fin_proceso is not None

    assert client.patch(url, headers=usuarios["ana"]["headers"]).status_code == 409
    assert client.patch(
        f"/api/procesamientos/{id_proc}/iniciar", headers=motor_headers
    ).status_code == 409


def test_admin_puede_cancelar_solicitud_ajena(client, usuarios, solicitud):
    r = client.patch(
        f"/api/procesamientos/{solicitud['id_procesamiento']}/cancelar",
        headers=usuarios["admin"]["headers"],
    )
    assert r.status_code == 200


# ---------- Listados (frontend) ----------

def test_listado_oculta_credenciales_en_mensaje_error(
    client, motor_headers, usuarios, solicitud
):
    id_proc = solicitud["id_procesamiento"]
    client.patch(f"/api/procesamientos/{id_proc}/iniciar", headers=motor_headers)
    client.patch(
        f"/api/procesamientos/{id_proc}",
        json={"estado": "error", "mensaje_error": "No se pudo abrir rtsp://user:pass@10.0.0.5/s"},
        headers=motor_headers,
    )

    r = client.get("/api/procesamientos", headers=usuarios["ana"]["headers"])
    assert r.status_code == 200
    assert r.json()[0]["mensaje_error"] == "No se pudo abrir rtsp://***@10.0.0.5/s"
    assert "pass" not in r.text


def test_listado_filtra_por_estado(client, usuarios, solicitud):
    h = usuarios["ana"]["headers"]
    assert len(client.get("/api/procesamientos?estado=pendiente", headers=h).json()) == 1
    assert client.get("/api/procesamientos?estado=completado", headers=h).json() == []


def test_catalogo_para_el_frontend(client, motor_headers, usuarios):
    _sync(client, motor_headers, _video("a.mp4"), _video("b.mp4"))
    _sync(client, motor_headers, _video("a.mp4"))  # b desaparece
    h = usuarios["ana"]["headers"]

    disponibles = client.get("/api/videos", headers=h).json()
    assert [v["nombre_archivo"] for v in disponibles] == ["a.mp4"]
    todos = client.get("/api/videos?solo_disponibles=false", headers=h).json()
    assert len(todos) == 2
    assert client.get("/api/videos").status_code == 401