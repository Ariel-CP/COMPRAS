import os
import sys

# Asegura que la raíz del proyecto esté en sys.path para permitir imports de `app`
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.db import SessionLocal
from app.services import auth_service, user_service

ROLES_PERMISSIONS = {
    "comprador": {
        "producto": (True, False),
        "sugerencia_compra": (True, True),
        "precio_compra_hist": (True, False),
        "proveedor": (True, True),
        "importacion_stock": (True, False),
    },
    "analista_compras": {
        "producto": (True, False),
        "precio_compra_hist": (True, False),
        "reporte_ia": (True, True),
        "sugerencia_compra": (True, False),
    },
    "planificador": {
        "plan_produccion_mensual": (True, True),
        "requerimiento_material_mensual": (True, True),
        "mbom": (True, False),
    },
    "operador_almacen": {
        "stock_disponible_mes": (True, True),
        "movimientos_stock": (True, True),
    },
    "integrador_erp": {
        "importacion_stock": (True, True),
        "mappeo_flexxus": (True, True),
    },
    "contabilidad": {
        "costo_producto": (True, False),
        "precio_compra_hist": (True, True),
    },
    "auditor": {
        "producto": (True, False),
        "precio_compra_hist": (True, False),
        "reporte_ia": (True, False),
        "logs": (True, False),
    },
    "analista_ia": {
        "reporte_ia": (True, True),
        "precio_compra_hist": (True, False),
        "plan_produccion_mensual": (True, False),
    },
    "proveedor": {
        "pedidos_proveedor": (True, False),
    },
    "viewer": {
        "producto": (True, False),
        "reportes": (True, False),
    },
}


def run_seed(dry_run: bool = False) -> None:
    db = SessionLocal()
    try:
        for rol_nombre, perms in ROLES_PERMISSIONS.items():
            rid = auth_service._ensure_rol(db, rol_nombre)
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
    except Exception as ex:
        db.rollback()
        print("Error durante seed:", ex)
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Seed roles y permisos base para COMPRAS")
    p.add_argument("--dry", action="store_true", help="No aplica cambios, solo muestra acciones")
    args = p.parse_args()
    run_seed(dry_run=args.dry)
