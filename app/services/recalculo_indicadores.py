import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session, sessionmaker

from app.core.tiempo import ahora_lima
from app.models.procesamiento import Procesamiento
from app.models.recalculo_indicador import RecalculoIndicador
from app.models.resultado_deteccion import ResultadoDeteccion
from app.services import indicador_service

logger = logging.getLogger(__name__)
INTERVALO_SEG = 5
MAX_REINTENTO_SEG = 300
TAMANO_LOTE = 50


def registrar_pendiente(db: Session, id_resultado: int) -> None:
    stmt = mysql_insert(RecalculoIndicador).values(
        id_resultado=id_resultado, disponible_desde=ahora_lima().replace(microsecond=0)
    )
    db.execute(stmt.on_duplicate_key_update(id_resultado=stmt.inserted.id_resultado))


def intentar(db: Session, id_resultado: int, id_zona: int, momento: datetime) -> None:
    try:
        with db.begin():
            # El bloqueo precede a cualquier lectura de las mediciones. Así un recálculo
            # concurrente de la misma zona no puede escribir sobre un resumen más nuevo.
            if not indicador_service.bloquear_zona(db, id_zona):
                return
            ahora = ahora_lima()
            pendiente = db.get(RecalculoIndicador, id_resultado, with_for_update=True)
            if pendiente is None or pendiente.disponible_desde > ahora:
                return
            try:
                with db.begin_nested():
                    indicador_service.actualizar_indicadores(db, id_zona, momento)
            except Exception:
                logger.exception("Falló el recálculo de indicadores del resultado %s", id_resultado)
                pendiente.intentos += 1
                espera = min(INTERVALO_SEG * 2 ** min(pendiente.intentos - 1, 6), MAX_REINTENTO_SEG)
                pendiente.disponible_desde = ahora_lima() + timedelta(seconds=espera)
            else:
                db.delete(pendiente)
    except Exception:
        # Si falla la transacción completa, la medición y su pendiente siguen guardados.
        logger.exception("No se completó el trabajo de indicadores del resultado %s", id_resultado)


def procesar_pendientes(abrir_sesion: sessionmaker[Session]) -> None:
    stmt = (
        select(RecalculoIndicador.id_resultado, Procesamiento.id_zona, ResultadoDeteccion.periodo_inicio)
        .join(ResultadoDeteccion, ResultadoDeteccion.id_resultado == RecalculoIndicador.id_resultado)
        .join(Procesamiento, Procesamiento.id_procesamiento == ResultadoDeteccion.id_procesamiento)
        .where(RecalculoIndicador.disponible_desde <= ahora_lima())
        .order_by(RecalculoIndicador.disponible_desde, RecalculoIndicador.id_resultado)
        .limit(TAMANO_LOTE)
    )
    with abrir_sesion() as db:
        candidatos = db.execute(stmt).all()
        db.rollback()
        for id_resultado, id_zona, momento in candidatos:
            intentar(db, id_resultado, id_zona, momento)


async def ejecutar_worker(abrir_sesion: sessionmaker[Session], detener: asyncio.Event) -> None:
    while not detener.is_set():
        try:
            await asyncio.to_thread(procesar_pendientes, abrir_sesion)
        except Exception:
            logger.exception("No se pudieron consultar los recálculos pendientes")
        try:
            await asyncio.wait_for(detener.wait(), timeout=INTERVALO_SEG)
        except TimeoutError:
            pass
