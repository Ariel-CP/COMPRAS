"""Semilla de usuario admin con rol y permisos base.

Uso:
    python scripts/seed_admin.py --email admin@example.com --password admin123
Opcionales:
    --nombre "Admin"
    --forms productos rubros stock plan mbom informes tipo_cambio
"""

import argparse
import sys
from pathlib import Path
from typing import Iterable, List

from sqlalchemy import text

# Permitir imports de la carpeta app al ejecutar el script directamente
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import SessionLocal  # noqa: E402
from app.services import auth_service  # noqa: E402

DEFAULT_FORMS = [
    "admin_backups",
    "productos",
    "rubros",
    "stock",
    "plan",
    "mbom",
    "informes",
    "tipo_cambio",
    "admin_usuarios",
    "admin_roles",
    "precios",
    "unidades",
]


def upsert_permissions(db, role_id: int, form_keys: Iterable[str]) -> None:
    for key in form_keys:
        db.execute(
            text(
                "INSERT INTO permiso_form (rol_id, form_key, puede_leer, puede_escribir) "
                "VALUES (:rid, :fk, 1, 1) "
                "ON DUPLICATE KEY UPDATE puede_leer=VALUES(puede_leer), puede_escribir=VALUES(puede_escribir)"
            ),
            {"rid": role_id, "fk": key},
        )


def ensure_user_with_roles(
    db,
    email: str,
    nombre: str,
    password: str,
    roles: List[str],
) -> None:
    existing = auth_service.get_user_by_email(db, email)
    if existing:
        hashed = auth_service.hash_password(password)
        db.execute(
            text(
                "UPDATE usuario SET nombre=:n, password_hash=:ph, activo=1 WHERE id=:uid"
            ),
            {"n": nombre, "ph": hashed, "uid": existing["id"]},
        )
        user_id = existing["id"]
    else:
        created = auth_service.create_user(db, email, nombre, password, roles)
        user_id = int(created["id"]) if created else None

    if user_id:
        for rol_nombre in roles:
            role_id = _get_role_id(db, rol_nombre)
            db.execute(
                text(
                    "INSERT IGNORE INTO usuario_rol (usuario_id, rol_id) VALUES (:uid, :rid)"
                ),
                {"uid": user_id, "rid": role_id},
            )


def _get_role_id(db, role_name: str) -> int:
    rid = db.execute(
        text("SELECT id FROM rol WHERE nombre=:n"), {"n": role_name}
    ).scalar()
    if not rid:
        raise RuntimeError(f"Rol {role_name} no encontrado luego de crearlo")
    return int(rid)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed admin user")
    parser.add_argument("--email", default="admin@example.com")
    parser.add_argument("--nombre", default="Admin")
    parser.add_argument("--password", default="admin123")
    parser.add_argument("--forms", nargs="*", default=DEFAULT_FORMS)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        role_id = auth_service.ensure_role(db, "admin")
        upsert_permissions(db, role_id, args.forms)
        ensure_user_with_roles(
            db,
            email=args.email,
            nombre=args.nombre,
            password=args.password,
            roles=["admin"],
        )
        db.commit()
        print(
            f"Usuario admin seed completado. Email={args.email}, roles=admin, forms={args.forms}"
        )
    except Exception as exc:  # pragma: no cover - script manual
        db.rollback()
        raise exc
    finally:
        db.close()


if __name__ == "__main__":  # pragma: no cover - entrypoint script
    main()
