from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.crud import camara as crud_camara
from app.crud import zona as crud_zona
from app.models.camara import Camara
from app.schemas.camara import CamaraCreate, CamaraPublica, CamaraUpdate

# Prefijo distinto a /api/camaras, que está reservado al motor
router = APIRouter(
    prefix="/admin/camaras",
    tags=["camaras"],
    dependencies=[Depends(get_current_user)],
)


def _a_publica(camara: Camara) -> CamaraPublica:
    """Convierte a la respuesta pública SIN url_stream."""
    publica = CamaraPublica.model_validate(camara)
    publica.tiene_url_stream = bool(camara.url_stream)
    return publica


def _camara_o_404(db: Session, id_camara: int) -> Camara:
    camara = crud_camara.obtener(db, id_camara)
    if camara is None:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    return camara


def _validar_zona(db: Session, id_zona: int) -> None:
    if crud_zona.obtener(db, id_zona) is None:
        raise HTTPException(status_code=422, detail="La zona indicada no existe")


@router.get("", response_model=list[CamaraPublica])
def listar_camaras(id_zona: int | None = None, db: Session = Depends(get_db)):
    return [_a_publica(c) for c in crud_camara.listar(db, id_zona)]


@router.get("/{id_camara}", response_model=CamaraPublica)
def obtener_camara(id_camara: int, db: Session = Depends(get_db)):
    return _a_publica(_camara_o_404(db, id_camara))


@router.post(
    "",
    response_model=CamaraPublica,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def crear_camara(datos: CamaraCreate, db: Session = Depends(get_db)):
    _validar_zona(db, datos.id_zona)
    return _a_publica(crud_camara.crear(db, datos))


@router.patch(
    "/{id_camara}", response_model=CamaraPublica, dependencies=[Depends(require_admin)]
)
def actualizar_camara(
    id_camara: int, datos: CamaraUpdate, db: Session = Depends(get_db)
):
    camara = _camara_o_404(db, id_camara)
    if datos.id_zona is not None and datos.id_zona != camara.id_zona:
        # Cambiar de zona rompería la coherencia con procesamientos históricos
        raise HTTPException(
            status_code=422,
            detail="No se puede cambiar la zona de una cámara; crea una nueva",
        )
    return _a_publica(crud_camara.actualizar(db, camara, datos))