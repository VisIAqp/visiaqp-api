from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hashear_password
from app.models.rol import Rol
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate


def listar(db: Session) -> list[Usuario]:
    return list(db.scalars(select(Usuario).order_by(Usuario.username)))


def obtener(db: Session, id_usuario: int) -> Usuario | None:
    return db.get(Usuario, id_usuario)


def existe_username_o_email(
    db: Session, username: str | None, email: str | None, excluir_id: int | None = None
) -> bool:
    condiciones = []
    if username:
        condiciones.append(Usuario.username == username)
    if email:
        condiciones.append(Usuario.email == email)
    if not condiciones:
        return False
    stmt = select(Usuario.id_usuario).where(
        condiciones[0] if len(condiciones) == 1 else (condiciones[0] | condiciones[1])
    )
    if excluir_id is not None:
        stmt = stmt.where(Usuario.id_usuario != excluir_id)
    return db.scalars(stmt).first() is not None


def listar_roles(db: Session) -> list[Rol]:
    return list(db.scalars(select(Rol).order_by(Rol.id_rol)))


def obtener_rol(db: Session, id_rol: int) -> Rol | None:
    return db.get(Rol, id_rol)


def crear(db: Session, datos: UsuarioCreate) -> Usuario:
    campos = datos.model_dump(exclude={"password"})
    usuario = Usuario(**campos, password_hash=hashear_password(datos.password))
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def actualizar(db: Session, usuario: Usuario, datos: UsuarioUpdate) -> Usuario:
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(usuario, campo, valor)
    db.commit()
    db.refresh(usuario)
    return usuario


def cambiar_password(db: Session, usuario: Usuario, password_nueva: str) -> None:
    usuario.password_hash = hashear_password(password_nueva)
    db.commit()