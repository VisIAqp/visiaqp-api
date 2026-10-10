from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Indicador, UmbralConcentracion
from app.services import indicador_service
from app.services.indicador_service import clasificar


# ---------- Clasificación (sin BD) ----------

@pytest.mark.parametrize(
    "valor, esperado",
    [(0, "bajo"), (9.99, "bajo"), (10, "medio"), (29.99, "medio"), (30, "alto"), (100, "alto")],
)
def test_clasificar_en_los_limites(valor, esperado):
    assert clasificar(Decimal(str(valor)), 10, 30) == esperado


# ---------- Helpers ----------

def _enviar(client, headers, ids, id_proc, cantidad, minuto):
    r = client.post(
        f"/api/procesamientos/{id_proc}/resultados",
        json={
            "id_zona": ids["id_zona"],
            "id_camara": ids["id_camara"],
            "periodo_inicio": f"2026-09-20T14:{minuto:02d}:00",
            "periodo_fin": f"2026-09-20T14:{minuto:02d}:10",
            "cantidad_peatones": cantidad,
            "confianza_promedio": 0.6,
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text


@pytest.fixture
def id_proc(client, motor_headers, datos_base):
    r = client.post(
        "/api/procesamientos",
        json={
            "id_zona": datos_base["id_zona"],
            "id_camara": datos_base["id_camara"],
            "tipo_fuente": "video",
            "ruta_archivo": "demo.mp4",
            "fecha_captura_inicio": "2026-09-20T14:00:00",
        },
        headers=motor_headers,
    )
    return r.json()["id_procesamiento"]


def _indicadores(abrir_sesion):
    with abrir_sesion() as db:
        filas = db.scalars(select(Indicador).order_by(Indicador.periodo_tipo)).all()
        return {i.periodo_tipo: i for i in filas}


# ---------- Cálculo al insertar ----------

def test_un_resultado_crea_indicador_hora_y_dia(
    client, motor_headers, datos_base, id_proc, abrir_sesion
):
    _enviar(client, motor_headers, datos_base, id_proc, 39, 30)

    ind = _indicadores(abrir_sesion)
    assert set(ind) == {"hora", "dia"}
    assert ind["hora"].periodo_inicio == datetime(2026, 9, 20, 14, 0)
    assert ind["hora"].periodo_fin == datetime(2026, 9, 20, 15, 0)
    assert ind["dia"].periodo_inicio == datetime(2026, 9, 20, 0, 0)
    assert ind["hora"].total_peatones == 39
    assert ind["hora"].max_peatones == 39
    assert ind["hora"].nivel_concentracion == "alto"  # 39 >= 30


def test_segundo_resultado_actualiza_sin_duplicar(
    client, motor_headers, datos_base, id_proc, abrir_sesion
):
    _enviar(client, motor_headers, datos_base, id_proc, 39, 30)
    _enviar(client, motor_headers, datos_base, id_proc, 11, 31)

    with abrir_sesion() as db:
        assert len(db.scalars(select(Indicador)).all()) == 2  # una hora + un día

    hora = _indicadores(abrir_sesion)["hora"]
    assert hora.total_peatones == 50
    assert hora.promedio_peatones == Decimal("25.00")
    assert hora.max_peatones == 39
    assert hora.nivel_concentracion == "medio"  # promedio 25: >=10 y <30


def test_resultados_de_horas_distintas_crean_indicadores_separados(
    client, motor_headers, datos_base, id_proc, abrir_sesion
):
    _enviar(client, motor_headers, datos_base, id_proc, 5, 30)
    r = client.post(
        f"/api/procesamientos/{id_proc}/resultados",
        json={
            "id_zona": datos_base["id_zona"],
            "id_camara": datos_base["id_camara"],
            "periodo_inicio": "2026-09-20T15:10:00",
            "periodo_fin": "2026-09-20T15:10:10",
            "cantidad_peatones": 7,
        },
        headers=motor_headers,
    )
    assert r.status_code == 201

    with abrir_sesion() as db:
        horas = db.scalars(select(Indicador).where(Indicador.periodo_tipo == "hora")).all()
        dias = db.scalars(select(Indicador).where(Indicador.periodo_tipo == "dia")).all()
    assert len(horas) == 2
    assert len(dias) == 1
    assert dias[0].total_peatones == 12


# ---------- Umbrales ----------

def test_usa_umbral_de_la_zona(client, motor_headers, datos_base, id_proc, abrir_sesion):
    with abrir_sesion() as db:
        umbral = db.scalars(select(UmbralConcentracion)).first()
        umbral.umbral_medio, umbral.umbral_alto = 50, 100
        db.commit()

    _enviar(client, motor_headers, datos_base, id_proc, 39, 30)
    assert _indicadores(abrir_sesion)["hora"].nivel_concentracion == "bajo"


def test_sin_umbral_usa_valores_por_defecto(
    client, motor_headers, datos_base, id_proc, abrir_sesion
):
    with abrir_sesion() as db:
        db.query(UmbralConcentracion).delete()
        db.commit()

    _enviar(client, motor_headers, datos_base, id_proc, 39, 30)
    assert _indicadores(abrir_sesion)["hora"].nivel_concentracion == "alto"  # defecto 10/30


# ---------- Resiliencia ----------

def test_si_falla_el_recalculo_el_resultado_se_guarda(
    client, motor_headers, datos_base, id_proc, abrir_sesion, monkeypatch
):
    def _falla(*args, **kwargs):
        raise RuntimeError("fallo simulado")

    monkeypatch.setattr(indicador_service, "actualizar_indicadores", _falla)

    r = client.post(
        f"/api/procesamientos/{id_proc}/resultados",
        json={
            "id_zona": datos_base["id_zona"],
            "id_camara": datos_base["id_camara"],
            "periodo_inicio": "2026-09-20T14:30:00",
            "periodo_fin": "2026-09-20T14:30:10",
            "cantidad_peatones": 20,
        },
        headers=motor_headers,
    )
    assert r.status_code == 201  # el motor no debe reintentar y duplicar

    from app.models import ResultadoDeteccion

    with abrir_sesion() as db:
        assert len(db.scalars(select(ResultadoDeteccion)).all()) == 1
        assert db.scalars(select(Indicador)).first() is None


def test_resultado_al_final_de_la_hora_cuenta_en_esa_hora(
    client, motor_headers, datos_base, id_proc, abrir_sesion
):
    r = client.post(
        f"/api/procesamientos/{id_proc}/resultados",
        json={
            "id_zona": datos_base["id_zona"],
            "id_camara": datos_base["id_camara"],
            "periodo_inicio": "2026-09-20T14:59:59.700000",
            "periodo_fin": "2026-09-20T15:00:09.700000",
            "cantidad_peatones": 12,
        },
        headers=motor_headers,
    )
    assert r.status_code == 201

    hora = _indicadores(abrir_sesion)["hora"]
    assert hora.periodo_inicio == datetime(2026, 9, 20, 14, 0)
    assert hora.total_peatones == 12