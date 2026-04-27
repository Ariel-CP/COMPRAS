import os
import sys

from sqlalchemy import text

# Asegura que la raíz del proyecto esté en sys.path para permitir imports de `app`
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.db import SessionLocal  # noqa: E402
from app.services import user_service  # noqa: E402

ROLES_PERMISSIONS = {
    "comprador": {
        "productos": (True, False),
        "proveedores": (True, True),
        "precios": (True, True),
        "stock": (True, False),
    },
    "analista_compras": {
        "productos": (True, False),
        "proveedores": (True, False),
        "precios": (True, True),
        "informes": (True, True),
    },
    "planificador": {
        "plan": (True, True),
        "mbom": (True, True),
    },
    "operador_almacen": {
        "stock": (True, True),
        "productos": (True, False),
    },
    "integrador_erp": {
        "stock": (True, True),
        "productos": (True, False),
    },
    "contabilidad": {
        "proveedores": (True, False),
        "precios": (True, True),
        "informes": (True, False),
    },
    "auditor": {
        "productos": (True, False),
        "proveedores": (True, False),
        "precios": (True, False),
        "plan": (True, False),
        "mbom": (True, False),
        "informes": (True, False),
    },
    "analista_ia": {
        "informes": (True, True),
        "precios": (True, False),
        "plan": (True, False),
    },
    "proveedor": {
        "productos": (True, False),
    },
    "viewer": {
        "productos": (True, False),
        "informes": (True, False),
    },
}


def run_seed(dry_run: bool = False) -> None:
    db = SessionLocal()
    try:
        for rol_nombre, perms in ROLES_PERMISSIONS.items():
            rid = _ensure_role(db, rol_nombre)
            print(f"Rol asegurado: {rol_nombre} (id={rid})")
            # preparar lista de permisos en el formato esperado por user_service.set_role_perms
            perms_list = [
                {
                    "form_key": fk,
                    "puede_leer": bool(vals[0]),
                    "puede_escribir": bool(vals[1]),
                }
                for fk, vals in perms.items()
            ]
            if dry_run:
                print(f"  Permisos (dry): {perms_list}")
            else:
                user_service.set_role_perms(db, rid, perms_list)
                print(f"  Permisos aplicados: {len(perms_list)}")
        if not dry_run:
            db.commit()
            print("Seed completado.")
    except RuntimeError:
        db.rollback()
        raise
    finally:
        db.close()


def _ensure_role(db, role_name: str) -> int:
    rid = db.execute(
        text("SELECT id FROM rol WHERE nombre=:n"),
        {"n": role_name},
    ).scalar()
    if rid:
        return int(rid)

    db.execute(
        text("INSERT INTO rol (nombre, descripcion) VALUES (:n, :d)"),
        {"n": role_name, "d": None},
    )
    rid = db.execute(text("SELECT LAST_INSERT_ID() AS id")).scalar()
    if not rid:
        raise RuntimeError(f"No se pudo crear/leer rol: {role_name}")
    return int(rid)


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Seed roles y permisos base para COMPRAS")
    p.add_argument("--dry", action="store_true", help="No aplica cambios, solo muestra acciones")
    args = p.parse_args()
    run_seed(dry_run=args.dry)
