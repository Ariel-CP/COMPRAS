#!/usr/bin/env python
"""Script de prueba para sincronización histórica BCRA."""

from app.db import SessionLocal
from app.services.tipo_cambio_sync_service import sync_bcra_historico
from datetime import date

def main():
    db = SessionLocal()
    try:
        # Sincronizar un rango corto: agosto 2026
        print("Iniciando prueba de sincronización histórica BCRA...")
        print("Rango: 2026-08-01 hasta 2026-08-31")
        print()
        
        resumen = sync_bcra_historico(
            db,
            desde=date(2026, 8, 1),
            hasta=date(2026, 8, 31),
        )
        
        print("=" * 60)
        print("RESULTADO DE LA SINCRONIZACIÓN")
        print("=" * 60)
        print(f"Período:      {resumen.fecha_desde} a {resumen.fecha_hasta}")
        print(f"Recibidos:    {resumen.recibidos}")
        print(f"Insertados:   {resumen.insertados}")
        print(f"Actualizados: {resumen.actualizados}")
        print(f"Sin cambios:  {resumen.sin_cambios}")
        print(f"Errores:      {resumen.errores}")
        print("=" * 60)
        
        # Consultar registros guardados
        if resumen.recibidos > 0:
            print()
            print("Primeros y últimos registros guardados:")
            from sqlalchemy import text
            
            query = text("""
                SELECT fecha, tipo, tasa, origen
                FROM tipo_cambio_hist
                WHERE moneda = 'USD' AND origen = 'OTRO'
                ORDER BY fecha ASC
                LIMIT 3
            """)
            result = db.execute(query).fetchall()
            print("\nPrimeros registros (ASC):")
            for row in result:
                print(f"  {row[0]} {row[1]}: {row[2]:.6f} (origen: {row[3]})")
            
            query = text("""
                SELECT fecha, tipo, tasa, origen
                FROM tipo_cambio_hist
                WHERE moneda = 'USD' AND origen = 'OTRO'
                ORDER BY fecha DESC
                LIMIT 3
            """)
            result = db.execute(query).fetchall()
            print("\nÚltimos registros (DESC):")
            for row in result:
                print(f"  {row[0]} {row[1]}: {row[2]:.6f} (origen: {row[3]})")
        
        db.commit()
        print("\n✅ Prueba completada exitosamente")
        return 0
        
    except Exception as exc:
        print(f"\n❌ Error: {exc}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()

if __name__ == "__main__":
    exit(main())
