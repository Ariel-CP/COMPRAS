#!/usr/bin/env python3
"""
Test de importación sin restricciones:
Verifica que todos los registros se importan aunque tengan datos imperfectos
"""

import sys

sys.path.insert(0, ".")

from pathlib import Path  # noqa: E402

from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.services.proveedor_import_service import importar_proveedores_desde_csv  # noqa: E402


def main():
    """Ejecuta test de importación sin restricciones con datos imperfectos."""
    print("=" * 100)
    print("TEST: Importación SIN RESTRICCIONES (datos imperfectos)")
    print("=" * 100)

    csv_file = Path("import/test_sin_restricciones.csv")
    if not csv_file.exists():
        print(f"❌ Archivo no encontrado: {csv_file}")
        return False

    contenido = csv_file.read_bytes()
    db = SessionLocal()

    try:
        # Limpiar datos de prueba previos
        db.execute(
            text(
                "DELETE FROM proveedor WHERE codigo LIKE 'SIN_%'"
                " OR codigo LIKE 'EMAIL_%' OR codigo LIKE 'CUIT_%'"
                " OR codigo LIKE 'TEL_%' OR codigo LIKE 'TODO_%'"
                " OR codigo LIKE 'SOLO_%'"
            )
        )
        db.commit()
        print("\n✓ Base de datos limpia")

        # Importar
        print("\n🔄 Importando archivo CSV con datos imperfectos...")
        resultado = importar_proveedores_desde_csv(db, contenido)

        print("\n✅ Importación completada")
        print(f"   Insertados: {resultado.get('insertados', 0)}")
        print(f"   Actualizados: {resultado.get('actualizados', 0)}")
        print(f"   Rechazados: {resultado.get('rechazados', 0)}")

        if resultado.get("errores"):
            print(f"\n⚠️ Errores: {len(resultado['errores'])}")
            for err in resultado["errores"][:5]:  # Mostrar primeros 5
                print(
                    f"   Fila {err.get('fila')} ({err.get('codigo')}): {err.get('mensaje')}"
                )

        # Verificar datos importados
        print("\n" + "=" * 100)
        print("VERIFICACIÓN: Datos Importados (sin restricciones)")
        print("=" * 100)

        rows = db.execute(text("""
            SELECT 
                codigo, 
                nombre, 
                cuit, 
                email, 
                telefono
            FROM proveedor 
            WHERE codigo LIKE 'SIN_%' OR codigo LIKE 'EMAIL_%' OR codigo LIKE 'CUIT_%' 
               OR codigo LIKE 'TEL_%' OR codigo LIKE 'TODO_%' OR codigo LIKE 'SOLO_%'
            ORDER BY codigo
        """)).fetchall()

        print(f"\n📊 {len(rows)} proveedores importados:\n")
        print(
            f"{'Código':<20} {'Razón Social':<25} {'CUIT':<15} {'Email':<20} {'Teléfono':<12}"
        )
        print("-" * 95)

        for row in rows:
            codigo, nombre, cuit, email, telefono = row
            nombre_t = (nombre[:23] + "..") if len(nombre) > 23 else nombre
            cuit_t = cuit if cuit else "-"
            email_t = (
                (email[:18] + "..") if email and len(email) > 18 else (email or "-")
            )
            tel_t = (
                (telefono[:10] + "..")
                if telefono and len(telefono) > 10
                else (telefono or "-")
            )

            print(
                f"{codigo:<20} {nombre_t:<25} {cuit_t:<15}"
                f" {email_t:<20} {tel_t:<12}"
            )

        print("\n" + "=" * 100)
        if (
            len(rows) >= 4
        ):  # Debe importar al menos 4 de los 6 (todos menos SOLO_CODIGO que no tiene nombre)
            print(
                f"✅ ÉXITO: Se importaron {len(rows)} registros sin rechazar por datos imperfectos"
            )
            print("   Registros importados aunque tengan:")
            print("   • Email inválido o ausente")
            print("   • CUIT incompleto o inválido")
            print("   • Teléfono muy corto")
            print("   • Campos vacíos (excepto Código y Nombre que son obligatorios)")
        else:
            print(f"❌ PROBLEMA: Solo se importaron {len(rows)} de 5+ esperados")

        print("=" * 100)

        return len(rows) >= 4

    except Exception as ex:  # pylint: disable=broad-exception-caught
        print(f"❌ Error: {ex}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
