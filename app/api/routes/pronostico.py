from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.tiempo import ahora_lima
from app.models import Camara, ModeloOcupacion, PronosticoOcupacion
from app.schemas.pronostico import PronosticoRespuesta
from app.services.pronostico import ESQUEMA, VIGENCIA, camara_apta


router = APIRouter(prefix="/pronosticos", tags=["pronósticos"], dependencies=[Depends(get_current_user)])


@router.get("/ocupacion", response_model=PronosticoRespuesta)
def ocupacion(id_camara: int = Query(ge=1), db: Session = Depends(get_db)):
    camara = db.get(Camara, id_camara)
    if camara is None:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    if not camara_apta(camara):
        return PronosticoRespuesta(id_camara=id_camara, estado="camara_no_apta")

    modelo = db.get(ModeloOcupacion, id_camara)
    if (modelo is None or modelo.firma_captura != camara.firma_captura
            or modelo.artefacto.get("esquema") != ESQUEMA):
        return PronosticoRespuesta(id_camara=id_camara, estado="sin_modelo")

    actual = db.get(PronosticoOcupacion, id_camara)
    ahora = ahora_lima()
    if (actual is None or actual.version_modelo != modelo.version
            or not actual.emitido_en <= ahora < actual.base_en + VIGENCIA):
        return PronosticoRespuesta(id_camara=id_camara, estado="sin_pronostico_vigente")

    return PronosticoRespuesta(
        id_camara=id_camara, estado="disponible", base_en=actual.base_en, emitido_en=actual.emitido_en,
        version_modelo=actual.version_modelo, estimaciones=actual.estimaciones,
    )
