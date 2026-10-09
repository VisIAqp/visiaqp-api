from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.db.database import get_db
from app.models.models import Procesamiento, ResultadoDeteccion, Zona

router = APIRouter(
    prefix="/api/procesamientos",
    tags=["Procesamientos e IA"]
)


# ==================== SCHEMAS ====================

class ProcesamientoCreate(BaseModel):
    id_zona: int
    id_camara: Optional[int] = None
    id_usuario: Optional[int] = None
    tipo_fuente: str = Field(..., description="imagen, video o stream")
    ruta_archivo: Optional[str] = None
    fecha_captura_inicio: datetime


class ResultadoDeteccionCreate(BaseModel):
    id_zona: Optional[int] = None
    id_camara: Optional[int] = None
    periodo_inicio: datetime
    periodo_fin: datetime
    cantidad_peatones: int = Field(..., ge=0)
    confianza_promedio: Optional[float] = None


class ProcesamientoUpdate(BaseModel):
    estado: str = Field(..., description="completado o error")
    fecha_fin_proceso: Optional[datetime] = None
    mensaje_error: Optional[str] = None


# ==================== ENDPOINTS ====================

@router.post("", status_code=status.HTTP_201_CREATED)
def crear_procesamiento(payload: ProcesamientoCreate, db: Session = Depends(get_db)):
    zona = db.query(Zona).filter(Zona.id_zona == payload.id_zona).first()
    if not zona:
        raise HTTPException(status_code=404, detail="La zona especificada no existe")

    nuevo_p = Procesamiento(
        id_zona=payload.id_zona,
        id_camara=payload.id_camara,
        id_usuario=payload.id_usuario,
        tipo_fuente=payload.tipo_fuente,
        ruta_archivo=payload.ruta_archivo,
        fecha_captura_inicio=payload.fecha_captura_inicio,
        estado="procesando"
    )
    db.add(nuevo_p)
    db.commit()
    db.refresh(nuevo_p)

    return {"id_procesamiento": nuevo_p.id_procesamiento}


@router.post("/{id_procesamiento}/resultados", status_code=status.HTTP_201_CREATED)
def agregar_resultado(id_procesamiento: int, payload: ResultadoDeteccionCreate, db: Session = Depends(get_db)):
    proc = db.query(Procesamiento).filter(Procesamiento.id_procesamiento == id_procesamiento).first()
    if not proc:
        raise HTTPException(status_code=404, detail="Procesamiento no encontrado")

    resultado = ResultadoDeteccion(
        id_procesamiento=id_procesamiento,
        periodo_inicio=payload.periodo_inicio,
        periodo_fin=payload.periodo_fin,
        cantidad_peatones=payload.cantidad_peatones,
        confianza_promedio=payload.confianza_promedio
    )
    db.add(resultado)
    db.commit()

    return {"mensaje": "Resultado de ventana registrado con éxito"}


@router.patch("/{id_procesamiento}")
def actualizar_procesamiento(id_procesamiento: int, payload: ProcesamientoUpdate, db: Session = Depends(get_db)):
    proc = db.query(Procesamiento).filter(Procesamiento.id_procesamiento == id_procesamiento).first()
    if not proc:
        raise HTTPException(status_code=404, detail="Procesamiento no encontrado")

    # Actualizar estado (completado o error)
    proc.estado = payload.estado

    # Asignar la fecha de cierre siempre con la hora actual para cumplir el CHECK constraint
    proc.fecha_fin_proceso = datetime.now()

    if payload.mensaje_error:
        proc.mensaje_error = payload.mensaje_error

    db.commit()
    return {"mensaje": f"Procesamiento actualizado a estado: {payload.estado}"}