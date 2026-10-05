from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.models.models import Camara, Zona
from app.schemas.schemas import CamaraCreate, CamaraResponse

router = APIRouter(
    prefix="/api/v1/camaras",
    tags=["Cámaras (CU011)"]
)

@router.get("/", response_model=List[CamaraResponse])
def obtener_camaras(db: Session = Depends(get_db)):
    """Obtiene el listado de todas las cámaras activas."""
    return db.query(Camara).filter(Camara.estado == "activa").all()

@router.post("/", response_model=CamaraResponse, status_code=status.HTTP_201_CREATED)
def crear_camara(camara_in: CamaraCreate, db: Session = Depends(get_db)):
    """Registra una nueva cámara asignándola a una zona existente."""
    # Validar que exista la zona
    zona = db.query(Zona).filter(Zona.id_zona == camara_in.id_zona).first()
    if not zona:
        raise HTTPException(status_code=404, detail="La zona asignada a la cámara no existe")

    nueva_camara = Camara(**camara_in.model_dump())
    db.add(nueva_camara)
    db.commit()
    db.refresh(nueva_camara)
    return nueva_camara