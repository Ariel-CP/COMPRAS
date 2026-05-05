#!/usr/bin/env python3
"""Script de prueba para validar actualización de proveedores"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import SessionLocal
from app.services.proveedor_import_service import importar_proveedores_desde_csv

def test_actualizacion():
    """Prueba la actualización de proveedores desde CSV"""
    
    csv_file = Path(__file__).parent.parent / "import" / "proveedores_test_update.csv"
    if not csv_file.exists():
        print(f"❌ Archivo no encontrado: {csv_file}")
        return False
    
    print(f"📖 Leyendo archivo de actualización: {csv_file.name}")
    contenido = csv_file.read_bytes()
    
    db = SessionLocal()
    try:
        print("🔄 Re-importando proveedores (con cambios)...")
        resultado = importar_proveedores_desde_csv(db, contenido)
        
        print("\n✅ Importación completada")
        print(f"   Insertados: {resultado.get('insertados', 0)}")
        print(f"   Actualizados: {resultado.get('actualizados', 0)}")
        print(f"   Rechazados: {resultado.get('rechazados', 0)}")
        
        # Verificar datos
        from sqlalchemy import text
        rows = db.execute(text("SELECT codigo, nombre, email FROM proveedor WHERE codigo LIKE 'TEST%' ORDER BY codigo")).fetchall()
        print("\n📊 Proveedores en BD:")
        for row in rows:
            print(f"   {row[0]}: {row[1]} ({row[2]})")
        
        return True
        
    except Exception as ex:
        print(f"❌ Error: {ex}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = test_actualizacion()
    sys.exit(0 if success else 1)
