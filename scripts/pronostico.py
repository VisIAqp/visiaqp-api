"""Ajusta un modelo por cámara y publica predicciones fuera del servidor HTTP."""
import argparse
from datetime import datetime, time, timedelta
import json
import sys
from time import sleep
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.core.database import SessionLocal
from app.core.tiempo import ahora_lima
from app.models import Camara, ModeloOcupacion, PronosticoOcupacion
from app.services.pronostico import (
    BLOQUE, ESQUEMA, ESPERA, HistorialInsuficiente, camara_apta, entrenar, inicio_bloque, predecir, serie_ocupacion,
)


def requiere_ajuste(modelo: ModeloOcupacion | None, firma: str, corte: datetime, intervalo: timedelta) -> bool:
    return (modelo is None or modelo.firma_captura != firma or modelo.artefacto.get("esquema") != ESQUEMA
            or corte - modelo.hasta_datos >= intervalo)


def ajustar(id_camara: int, dias: int, intervalo: timedelta | None = None) -> None:
    hasta = inicio_bloque(ahora_lima() - ESPERA)
    with SessionLocal() as db:
        camara = db.get(Camara, id_camara)
        if camara is None or not camara_apta(camara):
            if intervalo is not None:
                return
            raise ValueError("Elige una cámara fija, activa y con polígono")
        firma = camara.firma_captura
        actual = db.get(ModeloOcupacion, id_camara)
        if intervalo is not None and not requiere_ajuste(actual, firma, hasta, intervalo):
            return
        serie = serie_ocupacion(db, id_camara, firma, hasta - timedelta(days=dias), hasta)
        if not serie:
            raise HistorialInsuficiente("sin bloques de ocupación válidos para la captura actual")
        corte = max(serie)
        if intervalo is not None and not requiere_ajuste(actual, firma, corte, intervalo):
            return

    artefacto = entrenar(serie)
    with SessionLocal.begin() as db:
        camara = db.get(Camara, id_camara, with_for_update=True)
        if camara is None or not camara_apta(camara) or camara.firma_captura != firma:
            if intervalo is not None:
                return
            raise ValueError("La configuración de captura cambió durante el entrenamiento")
        actual = db.get(ModeloOcupacion, id_camara, with_for_update=True)
        if intervalo is not None and not requiere_ajuste(actual, firma, corte, intervalo):
            return
        if (actual and actual.firma_captura == firma and actual.artefacto.get("esquema") == ESQUEMA
                and actual.hasta_datos > corte):
            raise ValueError("Ya se publicó un modelo con datos más recientes")
        if actual is None:
            actual = ModeloOcupacion(id_camara=id_camara)
            db.add(actual)
        actual.firma_captura = firma
        actual.version = str(uuid4())
        actual.hasta_datos = corte
        actual.artefacto = artefacto
        version = actual.version

    print(json.dumps({"id_camara": id_camara, "version": version, "bloques_validos": len(serie),
                      "hasta_datos": corte.isoformat(), "horizontes": artefacto["horizontes"]}, indent=2))


def ajustar_pendientes(dias: int, intervalo: timedelta) -> None:
    with SessionLocal() as db:
        consulta = select(Camara).where(Camara.estado == "activa", Camara.tipo == "fija").order_by(Camara.id_camara)
        ids = [camara.id_camara for camara in db.scalars(consulta) if camara_apta(camara)]
    for id_camara in ids:
        try:
            ajustar(id_camara, dias, intervalo)
        except HistorialInsuficiente as error:
            print(f"Cámara {id_camara}: {error}", flush=True)


def programar_entrenamiento(dias: int, intervalo: timedelta) -> None:
    """Revisa al arrancar y luego cada día a las 03:00 de Lima."""
    while True:
        try:
            ajustar_pendientes(dias, intervalo)
        except OperationalError:
            print("MySQL no está disponible para entrenar; se reintentará en dos minutos.",
                  file=sys.stderr, flush=True)
            sleep(120)
            continue

        ahora = ahora_lima()
        siguiente = datetime.combine(ahora.date(), time(3))
        if siguiente <= ahora:
            siguiente += timedelta(days=1)
        print(f"Próxima revisión de entrenamiento: {siguiente:%Y-%m-%d %H:%M} (hora de Lima).", flush=True)
        while (espera := (siguiente - ahora_lima()).total_seconds()) > 0:
            sleep(min(espera, 60))


def generar(id_camara: int) -> str:
    base = inicio_bloque(ahora_lima() - ESPERA)
    with SessionLocal() as db:
        camara = db.get(Camara, id_camara)
        modelo = db.get(ModeloOcupacion, id_camara)
        if (camara is None or not camara_apta(camara) or modelo is None
                or camara.firma_captura != modelo.firma_captura
                or modelo.hasta_datos > base or modelo.artefacto.get("esquema") != ESQUEMA):
            return "sin modelo vigente"
        actual = db.get(PronosticoOcupacion, id_camara)
        if actual and actual.base_en == base and actual.version_modelo == modelo.version:
            return "ya publicado"
        firma, version = modelo.firma_captura, modelo.version
        serie = serie_ocupacion(db, id_camara, firma, base - 3 * BLOQUE, base)
        estimaciones = predecir(modelo.artefacto, serie, base)

    if not estimaciones:
        return "sin tres bloques recientes con cobertura suficiente"

    with SessionLocal.begin() as db:
        camara = db.get(Camara, id_camara, with_for_update=True)
        modelo = db.get(ModeloOcupacion, id_camara, with_for_update=True)
        if (camara is None or not camara_apta(camara) or camara.firma_captura != firma
                or modelo is None or modelo.version != version):
            return "la captura o el modelo cambió; vuelve a generar"
        actual = db.get(PronosticoOcupacion, id_camara, with_for_update=True)
        if actual and (actual.base_en > base or (actual.base_en == base and actual.version_modelo == version)):
            return "ya publicado"
        if actual is None:
            actual = PronosticoOcupacion(id_camara=id_camara)
            db.add(actual)
        actual.version_modelo = version
        actual.base_en = base
        actual.emitido_en = ahora_lima()
        actual.estimaciones = estimaciones
    return "publicado"


def emitir(id_camara: int | None) -> None:
    if id_camara is None:
        with SessionLocal() as db:
            ids = list(db.scalars(select(ModeloOcupacion.id_camara).order_by(ModeloOcupacion.id_camara)))
    else:
        ids = [id_camara]
    for camara in ids:
        estado = generar(camara)
        if estado != "ya publicado":
            print(f"Cámara {camara}: {estado}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    acciones = parser.add_subparsers(dest="accion", required=True)
    ajuste = acciones.add_parser("entrenar")
    ajuste.add_argument("--camara", type=int, required=True, help="ID de la cámara en vivo verificada")
    ajuste.add_argument("--dias", type=int, default=60, help="Días anteriores para entrenar (7 a 90)")
    pendientes = acciones.add_parser("entrenar-pendientes", help="Ajusta las cámaras elegibles con datos suficientes")
    pendientes.add_argument("--dias", type=int, default=60, help="Días anteriores para entrenar (7 a 90)")
    pendientes.add_argument("--cada-dias", type=int, default=7, help="Días de datos nuevos antes de reentrenar")
    pendientes.add_argument("--continuo", action="store_true", help="Revisa al arrancar y diariamente a las 03:00 de Lima")
    emision = acciones.add_parser("generar")
    emision.add_argument("--camara", type=int, help="ID de cámara; por defecto, todas las que tienen modelo")
    emision.add_argument("--continuo", action="store_true", help="Comprueba cada minuto si hay un bloque nuevo")
    args = parser.parse_args()
    if getattr(args, "camara", None) is not None and args.camara < 1:
        parser.error("--camara debe ser positivo")
    if args.accion in {"entrenar", "entrenar-pendientes"}:
        if not 7 <= args.dias <= 90:
            parser.error("--dias debe estar entre 7 y 90")
        try:
            if args.accion == "entrenar":
                ajustar(args.camara, args.dias)
            else:
                if not 1 <= args.cada_dias <= 90:
                    parser.error("--cada-dias debe estar entre 1 y 90")
                intervalo = timedelta(days=args.cada_dias)
                if args.continuo:
                    programar_entrenamiento(args.dias, intervalo)
                else:
                    ajustar_pendientes(args.dias, intervalo)
        except ModuleNotFoundError as error:
            if error.name != "sklearn":
                raise
            parser.exit(1, "Instala las dependencias con python -m pip install -r requirements.txt\n")
        except ValueError as error:
            parser.exit(1, f"{error}\n")
    elif args.continuo:
        try:
            while True:
                try:
                    emitir(args.camara)
                except OperationalError:
                    print("MySQL no está disponible para generar pronósticos; se reintentará en un minuto.",
                          file=sys.stderr, flush=True)
                sleep(60)
        except KeyboardInterrupt:
            return
    else:
        emitir(args.camara)


if __name__ == "__main__":
    main()
