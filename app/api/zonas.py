from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.models.models import Zona
from app.schemas.schemas import ZonaCreate, ZonaResponse

router = APIRouter(
    prefix="/api/v1/zonas",
    tags=["Zonas (CU010)"]
)


@router.get("/", response_model=List[ZonaResponse])
def obtener_zonas(db: Session = Depends(get_db)):
    """Obtiene el listado de todas las zonas registradas."""
    return db.query(Zona).all()


@router.get("/{id_zona}", response_model=ZonaResponse)
def obtener_zona_por_id(id_zona: int, db: Session = Depends(get_db)):
    """Obtiene el detalle de una zona por su ID."""
    zona = db.query(Zona).filter(Zona.id_zona == id_zona).first()
    if not zona:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    return zona


@router.post("/", response_model=ZonaResponse, status_code=status.HTTP_201_CREATED)
def crear_zona(zona_in: ZonaCreate, db: Session = Depends(get_db)):
    """Registra una nueva zona urbana."""
    # Validar si ya existe el nombre
    zona_existente = db.query(Zona).filter(Zona.nombre == zona_in.nombre).first()
    if zona_existente:
        raise HTTPException(status_code=400, detail="Ya existe una zona registrada con ese nombre")

    nueva_zona = Zona(**zona_in.model_dump())
    db.add(nueva_zona)
    db.commit()
    db.refresh(nueva_zona)
    return nueva_zona