from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.crud import indicador as crud_indicador
from app.models.zona import Zona
from app.schemas.indicador import (
    IndicadorActual,
    IndicadorOut,
    RecalcularRequest,
    RecalcularResultado,
)
from app.services import indicador_service

router = APIRouter(
    prefix="/indicadores",
    tags=["indicadores"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/actual", response_model=list[IndicadorActual])
def indicadores_actuales(
    nivel: Literal["bajo", "medio", "alto"] | None = None,
    db: Session = Depends(get_db),
):
    """Último indicador horario de cada zona activa.
    Con ?nivel=alto devuelve solo las zonas en concentración alta."""
    filas = crud_indicador.actuales(db, nivel)
    return [
        IndicadorActual(**IndicadorOut.model_validate(ind).model_dump(), nombre_zona=nombre)
        for ind, nombre in filas
    ]


@router.get("", response_model=list[IndicadorOut])
def historico(
    id_zona: int,
    periodo_tipo: Literal["hora", "dia"] = "hora",
    desde: datetime | None = None,
    hasta: datetime | None = None,
    limite: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    if db.get(Zona, id_zona) is None:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    return crud_indicador.listar(db, id_zona, periodo_tipo, desde, hasta, limite)


@router.post(
    "/recalcular",
    response_model=RecalcularResultado,
    dependencies=[Depends(require_admin)],
)
def recalcular(datos: RecalcularRequest, db: Session = Depends(get_db)):
    """Recalcula indicadores de una zona en un rango (p. ej. tras cambiar umbrales)."""
    if db.get(Zona, datos.id_zona) is None:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    horas = indicador_service.recalcular_rango(db, datos.id_zona, datos.desde, datos.hasta)
    return {"horas_recalculadas": horas}