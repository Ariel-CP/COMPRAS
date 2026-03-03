#!/usr/bin/env python3
"""Actualizar contraseña de usuario (dev).

Nota: este script ajusta `sys.path` para poder importar `app.*` al ejecutarse
desde la raíz; por eso se permite E402 (imports después de código).
"""
# ruff: noqa: E402

# Uso: python scripts/set_user_password.py
#
# Este script actualiza la contraseña del usuario por email (valores hardcodeados
# según solicitud). No exponer en producción.
import sys
from pathlib import Path

# Permitir imports relativos al ejecutar script desde la raíz
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

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
    sys.exit(2)

db = SessionLocal()
try:
    user = get_user_by_email(db, email)
    if not user:
        print(f"Usuario no encontrado: {email}", file=sys.stderr)
        sys.exit(3)
    ph = hash_password(new_password)
    db.execute(
        text("UPDATE usuario SET password_hash=:ph WHERE id=:id"),
        {"ph": ph, "id": user["id"]},
    )
    db.commit()
    print(f"Contraseña actualizada para: {email}")

    # Verificar autenticación
    ok = authenticate_user(db, email, new_password)
    if ok:
        print("Verificación OK: autenticación exitosa.")
        sys.exit(0)
    else:
        print(
            "Verificación FALLIDA: credenciales inválidas después de la actualización",
            file=sys.stderr,
        )
        sys.exit(4)
finally:
    db.close()
