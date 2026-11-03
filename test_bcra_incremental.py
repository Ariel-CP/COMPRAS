#!/usr/bin/env python
"""Prueba de sincronización incremental BCRA."""

from app.db import SessionLocal
from app.services.tipo_cambio_sync_service import sync_bcra_desde_ultima_fecha
from sqlalchemy import text

db = SessionLocal()

try:
    # Primero, ver cuál es la última fecha guardada
    query = text("""
        SELECT MAX(fecha) as max_fecha
        FROM tipo_cambio_hist
        WHERE moneda = 'USD' AND origen = 'OTRO' AND tipo = 'VENTA'
    """)
    result = db.execute(query).fetchone()
    print(f"Última fecha guardada: {result.max_fecha if result.max_fecha else 'ninguna'}")
    print()

    # Ahora sincronizar desde la última fecha
    print("Ejecutando sync_bcra_desde_ultima_fecha()...")
    resumen = sync_bcra_desde_ultima_fecha(db)
    print("Resultados:")
    print(f"  Fecha desde: {resumen.fecha_desde}")
    print(f"  Fecha hasta: {resumen.fecha_hasta}")
    print(f"  Recibidos:   {resumen.recibidos}")
    print(f"  Insertados:  {resumen.insertados}")
    print(f"  Actualizados: {resumen.actualizados}")
    print(f"  Errores:     {resumen.errores}")
    db.commit()
    print("\n✅ Sincronización incremental completada")
except Exception as exc:
    print(f"❌ Error: {exc}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
