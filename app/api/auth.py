from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import Usuario, Rol
from app.schemas.schemas import LoginRequest, TokenResponse, UsuarioCreate
from app.core.security import verificar_password, generar_hash_password, crear_token_acceso

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Autenticación y Seguridad (CU008)"]
)


@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    """
    Endpoint para autenticar usuarios.
    Permite el acceso usando el 'username' o el 'email' registrado.
    """
    # 1. Buscar el usuario por username o email
    usuario = db.query(Usuario).filter(
        (Usuario.username == credentials.username_o_email) |
        (Usuario.email == credentials.username_o_email)
    ).first()

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas: usuario o correo no encontrado"
        )

    # 2. Verificar el estado del usuario en la base de datos
    if usuario.estado != 'activo':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta del usuario se encuentra inactiva"
        )

    # 3. Validar la contraseña enviada usando bcrypt
    if not verificar_password(credentials.password, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas: contraseña no válida"
        )

    # 4. Obtener el nombre del rol del usuario
    rol = db.query(Rol).filter(Rol.id_rol == usuario.id_rol).first()
    nombre_rol = rol.nombre if rol else "Usuario"

    # 5. Generar el Token de Acceso JWT
    datos_token = {
        "sub": str(usuario.id_usuario),
        "username": usuario.username,
        "email": usuario.email,
        "rol": nombre_rol
    }

    access_token = crear_token_acceso(datos_token)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        id_usuario=usuario.id_usuario,
        username=usuario.username,
        nombre_completo=f"{usuario.nombres} {usuario.apellidos}",
        rol=nombre_rol
    )


@router.post("/registro-inicial", status_code=status.HTTP_201_CREATED)
def registrar_usuario(payload: UsuarioCreate, db: Session = Depends(get_db)):
    """
    Endpoint auxiliar para crear un usuario administrador con contraseña hasheada.
    """
    # Verificar si el username o email ya existen
    if db.query(Usuario).filter(Usuario.username == payload.username).first():
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe")
    if db.query(Usuario).filter(Usuario.email == payload.email).first():
        raise HTTPException(status_code=400, detail="El correo electrónico ya existe")

    # Hashear contraseña con bcrypt antes de almacenar
    hashed_pwd = generar_hash_password(payload.password)

    nuevo_usuario = Usuario(
        id_rol=payload.id_rol,
        nombres=payload.nombres,
        apellidos=payload.apellidos,
        username=payload.username,
        email=payload.email,
        password_hash=hashed_pwd,
        estado='activo'
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)

    return {"mensaje": f"Usuario {nuevo_usuario.username} registrado con éxito"}