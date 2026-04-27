#!/usr/bin/env python3
"""
Test de actualización: verificar que cambiar Activo en CSV actualiza la BD correctamente
"""

import sys
sys.path.insert(0, '.')

from pathlib import Path
from app.db import SessionLocal
from app.services.proveedor_import_service import importar_proveedores_desde_csv
from sqlalchemy import text

def main():
    print("=" * 100)
    print("TEST: Actualización de Campo Activo")
    print("=" * 100)
    
    db = SessionLocal()
    
    try:
        # Limpiar
        db.execute(text("DELETE FROM proveedor WHERE codigo LIKE 'UPDATE_%'"))
        db.commit()
        
        # PASO 1: Importar proveedores activos
        print("\n▶ PASO 1: Importar 3 proveedores ACTIVOS")
        csv1 = b"""Codigo;Razon Social;C.U.I.T.;Email;Activo
UPDATE_1;EMPRESA ORIGINAL;20-12345678-1;empresa@test.com;1
UPDATE_2;OTRA EMPRESA;20-87654321-2;otra@test.com;Si
UPDATE_3;TERCERA EMP;20-11111111-1;tercera@test.com;True
"""
        resultado1 = importar_proveedores_desde_csv(db, csv1)
        print(f"   Resultado: {resultado1['insertados']} insertados")
        
        # Verificar estado inicial
        rows1 = db.execute(text("""
            SELECT codigo, nombre, activo FROM proveedor 
            WHERE codigo LIKE 'UPDATE_%' ORDER BY codigo
        """)).fetchall()
        print(f"\n   Estado inicial en BD:")
        for codigo, nombre, activo in rows1:
            estado = "✅ ACTIVO" if activo else "❌ INACTIVO"
            print(f"      {codigo}: {estado}")
        
        # PASO 2: Importar CSV con cambios (algunos pasan a inactivos)
        print("\n▶ PASO 2: Actualizar - UPDATE_1 pasa a INACTIVO, UPDATE_2 se mantiene ACTIVO, UPDATE_3 pasa a INACTIVO")
        csv2 = b"""Codigo;Razon Social;C.U.I.T.;Email;Activo
UPDATE_1;EMPRESA ORIGINAL ACTUALIZADA;20-12345678-1;empresa@test.com;0
UPDATE_2;OTRA EMPRESA ACTUALIZADA;20-87654321-2;otra@test.com;1
UPDATE_3;TERCERA EMP ACTUALIZADA;20-11111111-1;tercera@test.com;No
"""
        resultado2 = importar_proveedores_desde_csv(db, csv2)
        print(f"   Resultado: {resultado2['actualizados']} actualizados")
        
        # Verificar estado final
        rows2 = db.execute(text("""
            SELECT codigo, nombre, activo FROM proveedor 
            WHERE codigo LIKE 'UPDATE_%' ORDER BY codigo
        """)).fetchall()
        print(f"\n   Estado final en BD:")
        print(f"\n{'Código':<15} {'Estado':<25} {'Esperado':<25} {'Resultado':<10}")
        print("-" * 75)
        
        all_success = True
        expectations = {
            'UPDATE_1': 0,  # Cambió de 1 a 0
            'UPDATE_2': 1,  # Se mantiene en 1
            'UPDATE_3': 0,  # Cambió de 1 a 0
        }
        
        for codigo, nombre, activo in rows2:
            estado = "✅ ACTIVO" if activo else "❌ INACTIVO"
            esperado = expectations.get(codigo, None)
            esperado_txt = "✅ ACTIVO" if esperado == 1 else "❌ INACTIVO"
            success = activo == esperado
            resultado = "✓" if success else "✗"
            
            if not success:
                all_success = False
            
            print(f"{codigo:<15} {estado:<25} {esperado_txt:<25} {resultado:<10}")
        
        print("\n" + "=" * 100)
        if all_success:
            print("✅ ÉXITO: El campo Activo se actualiza correctamente desde CSV")
        else:
            print("❌ PROBLEMA: El campo Activo no se actualiza correctamente")
        print("=" * 100)
        
        return all_success
        
    except Exception as ex:
        print(f"❌ Error: {ex}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
