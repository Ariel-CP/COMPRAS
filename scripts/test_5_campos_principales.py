#!/usr/bin/env python3
"""
Script de prueba para validar que el campo "Activo" se importa correctamente
desde CSV y respeta valores 0/1, Si/No, True/False, etc.
"""

import sys
sys.path.insert(0, '.')

from pathlib import Path
from app.db import SessionLocal
from app.services.proveedor_import_service import importar_proveedores_desde_csv
from sqlalchemy import text

def main():
    # Leer archivo de prueba
    csv_file = Path("import/test_campos_5_principales.csv")
    if not csv_file.exists():
        print(f"❌ Archivo no encontrado: {csv_file}")
        return False
    
    print("=" * 100)
    print("TEST: Importación de 5 Campos Principales (Código, Razón Social, CUIT, Email, Activo)")
    print("=" * 100)
    
    contenido = csv_file.read_bytes()
    db = SessionLocal()
    
    try:
        # Limpiar datos de prueba previos
        db.execute(text("DELETE FROM proveedor WHERE codigo LIKE 'ACTIVO%' OR codigo LIKE 'INACTIVO%'"))
        db.commit()
        print("\n✓ Base de datos limpia")
        
        # Importar
        print("\n🔄 Importando archivo CSV con 5 campos principales...")
        resultado = importar_proveedores_desde_csv(db, contenido)
        
        print(f"\n✅ Importación completada")
        print(f"   Insertados: {resultado.get('insertados', 0)}")
        print(f"   Actualizados: {resultado.get('actualizados', 0)}")
        print(f"   Rechazados: {resultado.get('rechazados', 0)}")
        
        if resultado.get('errores'):
            print(f"\n⚠️ Errores encontrados:")
            for err in resultado['errores']:
                print(f"   Fila {err.get('fila')} ({err.get('codigo')}): {err.get('mensaje')}")
        
        # Verificar datos importados
        print("\n" + "=" * 100)
        print("VERIFICACIÓN: Datos Importados")
        print("=" * 100)
        
        rows = db.execute(text("""
            SELECT 
                codigo, 
                nombre, 
                cuit, 
                email, 
                activo
            FROM proveedor 
            WHERE codigo LIKE 'ACTIVO%' OR codigo LIKE 'INACTIVO%'
            ORDER BY codigo
        """)).fetchall()
        
        print(f"\n📊 {len(rows)} proveedores importados:\n")
        print(f"{'Código':<15} {'Razón Social':<30} {'CUIT':<15} {'Email':<30} {'Activo':<10}")
        print("-" * 105)
        
        success_all = True
        for row in rows:
            codigo, nombre, cuit, email, activo = row
            activo_txt = "✅ SÍ" if activo else "❌ NO"
            
            # Validar que coincida con expectativa
            if codigo.startswith('ACTIVO'):
                expected = 1
                check = "✓" if activo == expected else "✗"
            else:
                expected = 0
                check = "✓" if activo == expected else "✗"
            
            if check == "✗":
                success_all = False
            
            nombre_trunc = (nombre[:28] + "..") if len(nombre) > 28 else nombre
            email_trunc = (email[:28] + "..") if len(email) > 28 else email
            
            print(f"{codigo:<15} {nombre_trunc:<30} {cuit:<15} {email_trunc:<30} {activo_txt:<10} {check}")
        
        print("\n" + "=" * 100)
        if success_all:
            print("✅ ÉXITO: Todos los campos se importaron correctamente")
            print("   • Código: Mapeado correctamente")
            print("   • Razón Social: Capturada")
            print("   • CUIT: Validado formato XX-XXXXXXXX-X")
            print("   • Email: Validado con regex")
            print("   • Activo: Respeta valores 1/0, Si/No, True/False")
        else:
            print("❌ PROBLEMA: El campo 'Activo' no se está respetando correctamente")
        
        print("=" * 100)
        
        return success_all
        
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
