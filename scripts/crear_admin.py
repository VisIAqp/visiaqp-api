"""
Crea el primer usuario Administrador.
Uso (desde la raíz):  python -m scripts.crear_admin
"""
import getpass

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hashear_password
from app.models import Rol, Usuario


def main() -> None:
    username = input("Username: ").strip()
    email = input("Email: ").strip()
    nombres = input("Nombres: ").strip()
    apellidos = input("Apellidos: ").strip()
    password = getpass.getpass("Contraseña (mín. 8, máx. 72 bytes): ")

    if not (8 <= len(password) and len(password.encode("utf-8")) <= 72):
        print("Contraseña inválida (8 caracteres mínimo, 72 bytes máximo).")
        return

    with SessionLocal() as db:
        rol = db.scalars(select(Rol).where(Rol.nombre == "Administrador")).first()
        if rol is None:
            print("No existe el rol 'Administrador'. Ejecuta antes el .sql.")
            return
        if db.scalars(
            select(Usuario).where(
                (Usuario.username == username) | (Usuario.email == email)
            )
        ).first():
            print("Ya existe un usuario con ese username o email.")
            return

        db.add(
            Usuario(
                id_rol=rol.id_rol,
                nombres=nombres,
                apellidos=apellidos,
                username=username,
                email=email,
                password_hash=hashear_password(password),
            )
        )
        db.commit()
        print(f"Administrador '{username}' creado.")


if __name__ == "__main__":
    main()