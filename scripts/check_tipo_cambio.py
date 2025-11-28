"""Script para verificar las tasas de cambio disponibles."""
import sys
from pathlib import Path
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import SessionLocal  # noqa: E402


def main():
    db = SessionLocal()
    try:
        print("\n=== Tasas de cambio disponibles ===\n")
        result = db.execute(
            text("""
                SELECT fecha, moneda, tipo, tasa, origen
                FROM tipo_cambio_hist
                ORDER BY moneda, fecha DESC
            """)
        )
        
        current_moneda = None
        for row in result:
            if current_moneda != row.moneda:
                if current_moneda is not None:
                    print()
                current_moneda = row.moneda
                print(f"--- {row.moneda} ---")
            
            print(f"{row.fecha} | {row.tipo:8s} | {row.tasa:12.6f} | {row.origen}")
        
        print("\n=== Productos con precio en USD_MAY ===\n")
        result2 = db.execute(
            text("""
                SELECT p.codigo, p.nombre, pch.precio_unitario, pch.moneda, pch.fecha_precio
                FROM precio_compra_hist pch
                JOIN producto p ON p.id = pch.producto_id
                WHERE pch.moneda = 'USD_MAY'
                ORDER BY pch.fecha_precio DESC
                LIMIT 10
            """)
        )
        
        for row in result2:
            print(f"{row.codigo:15s} | {row.nombre[:40]:40s} | {row.precio_unitario:10.4f} | {row.fecha_precio}")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
