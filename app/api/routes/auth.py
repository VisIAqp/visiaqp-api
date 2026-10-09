from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import crear_access_token, verificar_password
from app.models.usuario import Usuario
from app.schemas.auth import LoginRequest, Token, UsuarioActual

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(datos: LoginRequest, db: Session = Depends(get_db)):
    usuario = db.scalars(
        select(Usuario).where(Usuario.username == datos.username)
    ).first()

    hash_guardado = usuario.password_hash if usuario else None
    password_ok = verificar_password(datos.password, hash_guardado)

    if not usuario or not password_ok or usuario.estado != "activo":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = crear_access_token(usuario.id_usuario, usuario.rol.nombre)
    return Token(access_token=token)


@router.get("/me", response_model=UsuarioActual)
def me(usuario: Usuario = Depends(get_current_user)):
    return usuario