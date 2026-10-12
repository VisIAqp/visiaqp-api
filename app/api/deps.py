from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import comparar_claves, decodificar_token
from app.models.usuario import Usuario

bearer_scheme = HTTPBearer(auto_error=False)

_NO_AUTORIZADO = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No autenticado o token inválido",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credenciales: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    if credenciales is None:
        raise _NO_AUTORIZADO
    payload = decodificar_token(credenciales.credentials)
    if not payload or "sub" not in payload:
        raise _NO_AUTORIZADO
    try:
        id_usuario = int(payload["sub"])
    except (TypeError, ValueError):
        raise _NO_AUTORIZADO

    usuario = db.get(Usuario, id_usuario)
    if usuario is None or usuario.estado != "activo":
        raise _NO_AUTORIZADO
    return usuario


def require_admin(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    if usuario.rol.nombre != "Administrador":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol Administrador",
        )
    return usuario


def verificar_api_key_motor(x_api_key: str | None = Header(default=None)) -> None:
    """Protege los endpoints del motor. Si MOTOR_API_KEY está vacía, no valida."""
    esperada = settings.MOTOR_API_KEY
    if not esperada:
        return
    if not x_api_key or not comparar_claves(x_api_key, esperada):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida",
        )