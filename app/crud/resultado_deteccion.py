from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.resultado_deteccion import ResultadoDeteccion
from app.schemas.resultado_deteccion import ResultadoCreate


def crear(db: Session, id_procesamiento: int, datos: ResultadoCreate) -> ResultadoDeteccion:
    confianza = None
    if datos.confianza_promedio is not None:
        # 0-1 (motor) -> 0-100 (columna DECIMAL(5,2))
        confianza = Decimal(str(datos.confianza_promedio)) * 100
        confianza = confianza.quantize(Decimal("0.01"))

    resultado = ResultadoDeteccion(
        id_procesamiento=id_procesamiento,
        periodo_inicio=datos.periodo_inicio.replace(microsecond=0),
        periodo_fin=datos.periodo_fin.replace(microsecond=0),
        cantidad_peatones=datos.cantidad_peatones,
        confianza_promedio=confianza,
    )
    db.add(resultado)
    db.commit()
    db.refresh(resultado)
    return resultado