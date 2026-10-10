import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401  (registra las tablas en Base.metadata)
from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models import Camara, UmbralConcentracion, Zona

API_KEY_TEST = "clave-de-prueba"


@pytest.fixture(scope="session")
def engine_test():
    url = settings.TEST_DATABASE_URL
    if not url:
        pytest.skip("TEST_DATABASE_URL no configurada")

    nombre = make_url(url).database or ""
    if not nombre.endswith("_test") or url == settings.DATABASE_URL:
        pytest.exit(
            "TEST_DATABASE_URL debe apuntar a una base distinta cuyo nombre termine en '_test'",
            returncode=2,
        )

    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def abrir_sesion(engine_test):
    """Fábrica de sesiones. Úsala como `with abrir_sesion() as db:` para que cada
    consulta vea lo que ya confirmó la API (evita lecturas con snapshot viejo)."""
    return sessionmaker(bind=engine_test, autoflush=False)


@pytest.fixture
def client(engine_test, abrir_sesion, monkeypatch):
    monkeypatch.setattr(settings, "MOTOR_API_KEY", API_KEY_TEST)

    def _get_db_test():
        db = abrir_sesion()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db_test
    yield TestClient(app)
    app.dependency_overrides.clear()

    # Limpieza: la API hace commit, así que se vacían las tablas
    with engine_test.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for tabla in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f"DELETE FROM {tabla.name}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


@pytest.fixture
def motor_headers():
    return {"X-API-Key": API_KEY_TEST}


@pytest.fixture
def datos_base(client, abrir_sesion):
    """Zona 1 con cámara activa y umbral 10/30, una cámara inactiva y otra zona con su cámara."""
    with abrir_sesion() as db:
        zona = Zona(nombre="Zona Test")
        otra_zona = Zona(nombre="Otra Zona")
        db.add_all([zona, otra_zona])
        db.flush()

        cam = Camara(
            id_zona=zona.id_zona,
            nombre="Cam activa",
            url_stream="rtsp://user:pass@host/stream",
            zone_polygon=[[0.05, 0.1], [0.95, 0.1], [0.95, 0.95], [0.05, 0.95]],
        )
        cam_inactiva = Camara(
            id_zona=zona.id_zona,
            nombre="Cam inactiva",
            url_stream="rtsp://host/otra",
            estado="inactiva",
        )
        cam_otra_zona = Camara(
            id_zona=otra_zona.id_zona, nombre="Cam otra zona", url_stream="rtsp://host/z2"
        )
        db.add_all([cam, cam_inactiva, cam_otra_zona])
        db.add(UmbralConcentracion(id_zona=zona.id_zona, umbral_medio=10, umbral_alto=30))
        db.commit()

        return {
            "id_zona": zona.id_zona,
            "id_camara": cam.id_camara,
            "id_camara_otra_zona": cam_otra_zona.id_camara,
        }