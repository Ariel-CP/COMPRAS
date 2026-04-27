#!/usr/bin/env python3
"""Script de prueba para validar importación de proveedores"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import SessionLocal
from app.services.proveedor_import_service import importar_proveedores_desde_csv

def test_importacion():
    """Prueba la importación de proveedores desde CSV"""
    
    # Leer archivo de prueba
    csv_file = Path(__file__).parent.parent / "import" / "proveedores_test.csv"
    if not csv_file.exists():
        print(f"❌ Archivo no encontrado: {csv_file}")
        return False
    
    print(f"📖 Leyendo archivo: {csv_file}")
    contenido = csv_file.read_bytes()
    print(f"   Tamaño: {len(contenido)} bytes")
    
    # Ejecutar importación
    db = SessionLocal()
    try:
        print("\n🔄 Importando proveedores...")
        resultado = importar_proveedores_desde_csv(db, contenido)
        
        print(f"\n✅ Importación completada")
        print(f"   Status: {resultado.get('status', 'N/A')}")
        print(f"   Insertados: {resultado.get('insertados', 0)}")
        print(f"   Actualizados: {resultado.get('actualizados', 0)}")
        print(f"   Rechazados: {resultado.get('rechazados', 0)}")
        
        if resultado.get('errores'):
            print(f"\n⚠️ Errores encontrados: {len(resultado['errores'])}")
            for err in resultado['errores'][:5]:  # Mostrar primeros 5
                print(f"   Fila {err.get('fila')}: {err.get('mensaje')}")
        
        return resultado.get('status') == 'success'
        
    except Exception as ex:
        print(f"❌ Error: {ex}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = test_importacion()
    sys.exit(0 if success else 1)
