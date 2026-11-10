from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.resultado_deteccion import ResultadoDeteccion
from app.schemas.resultado_deteccion import ResultadoCreate


def crear(db: Session, id_procesamiento: int, datos: ResultadoCreate) -> ResultadoDeteccion:
    confianza = None
    if datos.confianza_promedio is not None:
        # 0-1 (motor) -> 0-100 (columna DECIMAL(5,2))
        confianza = Decimal(str(datos.confianza_promedio)) * 100
        confianza = confianza.quantize(Decimal("0.01"))

    if datos.clave_ventana:
        existente = db.scalar(select(ResultadoDeteccion).where(
            ResultadoDeteccion.id_procesamiento == id_procesamiento,
            ResultadoDeteccion.clave_ventana == datos.clave_ventana,
        ).with_for_update())
        if existente is not None:
            esperados = {
                "periodo_inicio": datos.periodo_inicio.replace(microsecond=0),
                "periodo_fin": datos.periodo_fin.replace(microsecond=0),
                "cantidad_peatones": datos.cantidad_peatones,
                "confianza_promedio": confianza,
                "promedio_presentes": None if datos.promedio_presentes is None else Decimal(str(datos.promedio_presentes)).quantize(Decimal("0.0001")),
                "max_presentes": datos.max_presentes,
                "segundos_observados": None if datos.segundos_observados is None else Decimal(str(datos.segundos_observados)).quantize(Decimal("0.0001")),
            }
            if any(getattr(existente, campo) != valor for campo, valor in esperados.items()):
                raise ValueError("La clave de ventana ya existe con datos diferentes")
            db.commit()
            return existente
    resultado = ResultadoDeteccion(
        id_procesamiento=id_procesamiento,
        clave_ventana=datos.clave_ventana,
        periodo_inicio=datos.periodo_inicio.replace(microsecond=0),
        periodo_fin=datos.periodo_fin.replace(microsecond=0),
        cantidad_peatones=datos.cantidad_peatones,
        promedio_presentes=datos.promedio_presentes,
        max_presentes=datos.max_presentes,
        segundos_observados=datos.segundos_observados,
        confianza_promedio=confianza,
    )
    db.add(resultado)
    db.commit()
    db.refresh(resultado)
    return resultado