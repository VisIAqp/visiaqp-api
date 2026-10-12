from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.crud import usuario as crud_usuario
from app.models.usuario import Usuario
from app.schemas.rol import RolOut
from app.schemas.usuario import (
    CambiarPassword,
    UsuarioCreate,
    UsuarioOut,
    UsuarioUpdate,
)

router = APIRouter(
    prefix="/usuarios", tags=["usuarios"], dependencies=[Depends(require_admin)]
)


def _usuario_o_404(db: Session, id_usuario: int) -> Usuario:
    usuario = crud_usuario.obtener(db, id_usuario)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return usuario


def _validar_rol(db: Session, id_rol: int) -> None:
    if crud_usuario.obtener_rol(db, id_rol) is None:
        raise HTTPException(status_code=422, detail="El rol indicado no existe")


@router.get("/roles", response_model=list[RolOut])
def listar_roles(db: Session = Depends(get_db)):
    return crud_usuario.listar_roles(db)


@router.get("", response_model=list[UsuarioOut])
def listar_usuarios(db: Session = Depends(get_db)):
    return crud_usuario.listar(db)


@router.get("/{id_usuario}", response_model=UsuarioOut)
def obtener_usuario(id_usuario: int, db: Session = Depends(get_db)):
    return _usuario_o_404(db, id_usuario)


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def crear_usuario(datos: UsuarioCreate, db: Session = Depends(get_db)):
    _validar_rol(db, datos.id_rol)
    if crud_usuario.existe_username_o_email(db, datos.username, datos.email):
        raise HTTPException(status_code=409, detail="Username o email ya registrado")
    return crud_usuario.crear(db, datos)


@router.patch("/{id_usuario}", response_model=UsuarioOut)
def actualizar_usuario(
    id_usuario: int,
    datos: UsuarioUpdate,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin),
):
    usuario = _usuario_o_404(db, id_usuario)

    if datos.id_rol is not None:
        _validar_rol(db, datos.id_rol)
    if datos.email and crud_usuario.existe_username_o_email(
        db, None, datos.email, excluir_id=id_usuario
    ):
        raise HTTPException(status_code=409, detail="Email ya registrado")

    # Un admin no puede dejarse sin acceso a sí mismo
    if usuario.id_usuario == admin.id_usuario:
        if datos.estado == "inactivo":
            raise HTTPException(
                status_code=409, detail="No puedes desactivar tu propia cuenta"
            )
        if datos.id_rol is not None and datos.id_rol != usuario.id_rol:
            raise HTTPException(
                status_code=409, detail="No puedes cambiar tu propio rol"
            )

    return crud_usuario.actualizar(db, usuario, datos)


@router.put("/{id_usuario}/password", status_code=status.HTTP_204_NO_CONTENT)
def cambiar_password(
    id_usuario: int, datos: CambiarPassword, db: Session = Depends(get_db)
):
    usuario = _usuario_o_404(db, id_usuario)
    crud_usuario.cambiar_password(db, usuario, datos.password_nueva)