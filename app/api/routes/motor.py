from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import camara as crud_camara
from app.crud import procesamiento as crud_proc
from app.crud import resultado_deteccion as crud_resultado
from app.schemas.camara import CamaraMotor
from app.schemas.procesamiento import (
    ProcesamientoCerrado,
    ProcesamientoCierre,
    ProcesamientoCreado,
    ProcesamientoCreate,
)
from app.schemas.resultado_deteccion import ResultadoCreado, ResultadoCreate

# Contrato con visiaqp-ai: NO cambiar rutas ni payloads sin avisar.
router = APIRouter(tags=["motor"])


@router.get("/camaras", response_model=list[CamaraMotor])
def listar_camaras(db: Session = Depends(get_db)):
    return crud_camara.listar_activas(db)


@router.post(
    "/procesamientos",
    response_model=ProcesamientoCreado,
    status_code=status.HTTP_201_CREATED,
)
def crear_procesamiento(datos: ProcesamientoCreate, db: Session = Depends(get_db)):
    if datos.id_camara is not None:
        if not crud_camara.obtener_en_zona(db, datos.id_camara, datos.id_zona):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La cámara no existe o no pertenece a la zona indicada",
            )
    proc = crud_proc.crear(db, datos)
    return {"id_procesamiento": proc.id_procesamiento}


@router.post(
    "/procesamientos/{id_procesamiento}/resultados",
    response_model=ResultadoCreado,
    status_code=status.HTTP_201_CREATED,
)
def registrar_resultado(
    id_procesamiento: int, datos: ResultadoCreate, db: Session = Depends(get_db)
):
    proc = crud_proc.obtener(db, id_procesamiento)
    if not proc:
        raise HTTPException(status_code=404, detail="Procesamiento no encontrado")
    if proc.estado != "procesando":
        raise HTTPException(
            status_code=409,
            detail=f"El procesamiento está en estado '{proc.estado}', no acepta resultados",
        )
    if datos.id_zona != proc.id_zona or (
        datos.id_camara is not None and datos.id_camara != proc.id_camara
    ):
        raise HTTPException(
            status_code=422,
            detail="id_zona/id_camara no coinciden con el procesamiento",
        )

    resultado = crud_resultado.crear(db, id_procesamiento, datos)
    return {"id_resultado": resultado.id_resultado}


@router.patch("/procesamientos/{id_procesamiento}", response_model=ProcesamientoCerrado)
def cerrar_procesamiento(
    id_procesamiento: int, datos: ProcesamientoCierre, db: Session = Depends(get_db)
):
    proc = crud_proc.obtener(db, id_procesamiento)
    if not proc:
        raise HTTPException(status_code=404, detail="Procesamiento no encontrado")
    proc = crud_proc.cerrar(db, proc, datos)
    return {"id_procesamiento": proc.id_procesamiento, "estado": proc.estado}