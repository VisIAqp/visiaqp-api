import hmac
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

# Hash válido de relleno para igualar tiempos cuando el usuario no existe
_HASH_FALSO = bcrypt.hashpw(b"relleno-timing", bcrypt.gensalt()).decode()


def hashear_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_password(password: str, password_hash: str | None) -> bool:
    """Siempre ejecuta bcrypt, aunque no exista hash, para no filtrar por tiempo."""
    hash_a_usar = (password_hash or _HASH_FALSO).encode("utf-8")
    try:
        ok = bcrypt.checkpw(password.encode("utf-8"), hash_a_usar)
    except ValueError:
        return False
    return ok and password_hash is not None


def crear_access_token(id_usuario: int, rol: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": str(id_usuario), "rol": rol, "exp": exp}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decodificar_token(token: str) -> dict | None:
    """Devuelve el payload o None si el token es inválido o expiró."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        return None


def comparar_claves(a: str, b: str) -> bool:
    """Comparación en tiempo constante."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))