import jwt
from datetime import datetime, timedelta, timezone
import bcrypt

# Parámetros de configuración para JWT
SECRET_KEY = "visiaqp_secret_key_super_segura_debe_estar_en_el_env"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120


def verificar_password(password_plano: str, password_hash: str) -> bool:
    """Verifica si la contraseña ingresada coincide con el hash almacenado en la BD."""
    return bcrypt.checkpw(
        password_plano.encode('utf-8'),
        password_hash.encode('utf-8')
    )


def generar_hash_password(password_plano: str) -> str:
    """Genera un hash bcrypt seguro para guardar en la base de datos."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_plano.encode('utf-8'), salt).decode('utf-8')


def crear_token_acceso(data: dict, expiracion_minutos: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    """Genera un Token de Acceso JWT firmado."""
    payload = data.copy()
    expira = datetime.now(timezone.utc) + timedelta(minutes=expiracion_minutos)
    payload.update({"exp": expira})

    token_jwt = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token_jwt