#!/usr/bin/env python3
"""Actualizar contrasena de usuario (dev)."""

# Uso: python scripts/set_user_password.py
#
# Este script actualiza la contraseña del usuario por email (valores hardcodeados
# según solicitud). No exponer en producción.
import sys
from pathlib import Path


def main() -> int:

    # Permitir imports relativos al ejecutar script desde la raiz.
    root_dir = Path(__file__).resolve().parents[2]
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    from sqlalchemy import text

    from app.db import SessionLocal
    from app.services.auth_service import (
        authenticate_user,
        get_user_by_email,
        hash_password,
    )

    email = "acepeda@ecotermo.lan"
    new_password = "2211"

    if not email or not new_password:
        print("Email y password requeridos", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        user = get_user_by_email(db, email)
        if not user:
            print(f"Usuario no encontrado: {email}", file=sys.stderr)
            return 3

        ph = hash_password(new_password)
        db.execute(
            text("UPDATE usuario SET password_hash=:ph WHERE id=:id"),
            {"ph": ph, "id": user["id"]},
        )
        db.commit()
        print(f"Contrasena actualizada para: {email}")

        ok = authenticate_user(db, email, new_password)
        if ok:
            print("Verificacion OK: autenticacion exitosa.")
            return 0

        print(
            "Verificacion FALLIDA: credenciales invalidas despues de la actualizacion",
            file=sys.stderr,
        )
        return 4
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
