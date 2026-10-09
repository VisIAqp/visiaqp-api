from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from app.models.indicador import Indicador
from app.models.procesamiento import Procesamiento
from app.models.resultado_deteccion import ResultadoDeteccion
from app.models.umbral_concentracion import UmbralConcentracion

# Se usan si la zona aún no tiene umbral configurado
UMBRAL_MEDIO_DEFECTO = 10
UMBRAL_ALTO_DEFECTO = 30


def _limites(momento: datetime, tipo: str) -> tuple[datetime, datetime]:
    if tipo == "hora":
        inicio = momento.replace(minute=0, second=0, microsecond=0)
        return inicio, inicio + timedelta(hours=1)
    inicio = momento.replace(hour=0, minute=0, second=0, microsecond=0)
    return inicio, inicio + timedelta(days=1)


def clasificar(valor: Decimal | float, umbral_medio: int, umbral_alto: int) -> str:
    if valor >= umbral_alto:
        return "alto"
    if valor >= umbral_medio:
        return "medio"
    return "bajo"


def _umbrales(db: Session, id_zona: int) -> tuple[int, int]:
    umbral = db.scalars(
        select(UmbralConcentracion).where(UmbralConcentracion.id_zona == id_zona)
    ).first()
    if umbral is None:
        return UMBRAL_MEDIO_DEFECTO, UMBRAL_ALTO_DEFECTO
    return umbral.umbral_medio, umbral.umbral_alto


def recalcular(db: Session, id_zona: int, momento: datetime, tipo: str) -> bool:
    """Recalcula (upsert) el indicador del periodo que contiene `momento`.
    Devuelve False si no hay resultados en ese periodo."""
    inicio, fin = _limites(momento, tipo)

    stmt = (
        select(
            func.coalesce(func.sum(ResultadoDeteccion.cantidad_peatones), 0),
            func.avg(ResultadoDeteccion.cantidad_peatones),
            func.max(ResultadoDeteccion.cantidad_peatones),
            func.count(),
        )
        .select_from(ResultadoDeteccion)
        .join(
            Procesamiento,
            Procesamiento.id_procesamiento == ResultadoDeteccion.id_procesamiento,
        )
        .where(
            Procesamiento.id_zona == id_zona,
            ResultadoDeteccion.periodo_inicio >= inicio,
            ResultadoDeteccion.periodo_inicio < fin,
        )
    )
    total, promedio, maximo, cantidad = db.execute(stmt).one()
    if cantidad == 0:
        return False

    promedio = Decimal(promedio).quantize(Decimal("0.01"))
    medio, alto = _umbrales(db, id_zona)
    nivel = clasificar(promedio, medio, alto)

    insert_stmt = mysql_insert(Indicador).values(
        id_zona=id_zona,
        periodo_tipo=tipo,
        periodo_inicio=inicio,
        periodo_fin=fin,
        total_peatones=int(total),
        promedio_peatones=promedio,
        max_peatones=int(maximo),
        nivel_concentracion=nivel,
    )
    upsert = insert_stmt.on_duplicate_key_update(
        periodo_fin=insert_stmt.inserted.periodo_fin,
        total_peatones=insert_stmt.inserted.total_peatones,
        promedio_peatones=insert_stmt.inserted.promedio_peatones,
        max_peatones=insert_stmt.inserted.max_peatones,
        nivel_concentracion=insert_stmt.inserted.nivel_concentracion,
        fecha_calculo=func.now(),
    )
    db.execute(upsert)
    db.commit()
    return True


def actualizar_indicadores(db: Session, id_zona: int, momento: datetime) -> None:
    """Se llama tras insertar un resultado: actualiza la hora y el día afectados."""
    recalcular(db, id_zona, momento, "hora")
    recalcular(db, id_zona, momento, "dia")


def recalcular_rango(db: Session, id_zona: int, desde: datetime, hasta: datetime) -> int:
    """Recalcula hora a hora (y los días tocados) en un rango. Útil tras cambiar
    umbrales o si algún recálculo automático falló. Devuelve las horas con datos."""
    actual = desde.replace(minute=0, second=0, microsecond=0)
    horas = 0
    dias_vistos: set[datetime] = set()
    while actual < hasta:
        if recalcular(db, id_zona, actual, "hora"):
            horas += 1
            dia = actual.replace(hour=0)
            if dia not in dias_vistos:
                recalcular(db, id_zona, actual, "dia")
                dias_vistos.add(dia)
        actual += timedelta(hours=1)
    return horas