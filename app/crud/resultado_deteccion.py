from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.tiempo import ahora_lima
from app.models.resultado_deteccion import ResultadoDeteccion
from app.schemas.resultado_deteccion import ResultadoCreate


def crear(db: Session, id_procesamiento: int, datos: ResultadoCreate) -> ResultadoDeteccion:
    confianza = None
    if datos.confianza_promedio is not None:
        # 0-1 (motor) -> 0-100 (columna DECIMAL(5,2))
        confianza = Decimal(str(datos.confianza_promedio)) * 100
        confianza = confianza.quantize(Decimal("0.01"))

    valores = {
        "periodo_inicio": datos.periodo_inicio,
        "periodo_fin": datos.periodo_fin,
        "cantidad_peatones": datos.cantidad_peatones,
        "confianza_promedio": confianza,
        "max_presentes": datos.max_presentes,
    }
    for campo in ("promedio_presentes", "segundos_observados"):
        valor = getattr(datos, campo)
        valores[campo] = None if valor is None else Decimal(str(valor)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP)

    if datos.clave_ventana:
        existente = db.scalar(select(ResultadoDeteccion).where(
            ResultadoDeteccion.id_procesamiento == id_procesamiento,
            ResultadoDeteccion.clave_ventana == datos.clave_ventana,
        ).with_for_update())
        if existente is not None:
            esperados = valores.copy()
            if existente.recibido_en is None:
                # Los reintentos de ventanas guardadas antes de la migración conservan su identidad.
                for campo in ("periodo_inicio", "periodo_fin"):
                    esperados[campo] = esperados[campo].replace(microsecond=0)
            if any(getattr(existente, campo) != valor for campo, valor in esperados.items()):
                raise ValueError("La clave de ventana ya existe con datos diferentes")
            db.commit()
            return existente
    resultado = ResultadoDeteccion(
        id_procesamiento=id_procesamiento,
        clave_ventana=datos.clave_ventana,
        recibido_en=ahora_lima(),
        **valores,
    )
    db.add(resultado)
    db.commit()
    db.refresh(resultado)
    return resultado
