from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.database import get_db
from app.models.models import Procesamiento, ResultadoDeteccion, Zona, Camara
from app.schemas.schemas import ConteosLoteCreate, ConteosLoteResponse

router = APIRouter(
    prefix="/api/v1/conteos",
    tags=["Guardado de Conteos (CU003, CU004)"]
)

@router.post("/", response_model=ConteosLoteResponse, status_code=status.HTTP_201_CREATED)
def registrar_conteos(payload: ConteosLoteCreate, db: Session = Depends(get_db)):
    """
    Endpoint consumido por el módulo de IA / OpenCV.
    Crea la sesión en 'procesamiento' e inserta sus lecturas en 'resultado_deteccion'.
    """
    # 1. Validar que la zona exista
    zona = db.query(Zona).filter(Zona.id_zona == payload.id_zona).first()
    if not zona:
        raise HTTPException(status_code=404, detail="La zona especificada no existe")

    # 2. Validar cámara si fue enviada
    if payload.id_camara:
        camara = db.query(Camara).filter(
            Camara.id_camara == payload.id_camara,
            Camara.id_zona == payload.id_zona
        ).first()
        if not camara:
            raise HTTPException(status_code=404, detail="La cámara no existe o no pertenece a la zona indicada")

    # 3. Crear el registro en la tabla 'procesamiento'
    nuevo_procesamiento = Procesamiento(
        id_zona=payload.id_zona,
        id_camara=payload.id_camara,
        id_usuario=payload.id_usuario,
        tipo_fuente=payload.tipo_fuente,
        ruta_archivo=payload.ruta_archivo,
        fecha_captura_inicio=payload.fecha_captura_inicio,
        fecha_inicio_proceso=datetime.now(),
        fecha_fin_proceso=datetime.now(),
        estado='completado'
    )
    db.add(nuevo_procesamiento)
    db.flush()  # Genera el id_procesamiento autoincremental sin hacer commit aún

    # 4. Insertar las ventanas de conteo en 'resultado_deteccion'
    registros_deteccion = []
    for det in payload.detecciones:
        registro = ResultadoDeteccion(
            id_procesamiento=nuevo_procesamiento.id_procesamiento,
            periodo_inicio=det.periodo_inicio,
            periodo_fin=det.periodo_fin,
            cantidad_peatones=det.cantidad_peatones,
            confianza_promedio=det.confianza_promedio
        )
        registros_deteccion.append(registro)

    db.add_all(registros_deteccion)
    db.commit()  # Confirma ambas inserciones en la BD de MySQL

    return ConteosLoteResponse(
        mensaje="Conteos e historial registrados con éxito",
        id_procesamiento=nuevo_procesamiento.id_procesamiento,
        total_registros_guardados=len(registros_deteccion)
    )