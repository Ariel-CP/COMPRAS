#!/usr/bin/env python
"""Test: sincronización BCRA USD (fuente confiable BCRA API pública)."""
import sys
from datetime import date
from decimal import Decimal

# Agregar directorio app al path
sys.path.insert(0, str(__file__).rsplit("\\", 1)[0])

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.tipo_cambio_sync_service import (
    sync_bcra_historico,
    obtener_ultima_fecha_bcra,
)

# Conectar a base de datos
settings = get_settings()
engine = create_engine(
    settings.database_url,
    echo=False,
)

db = Session(engine)

print("=" * 70)
print("TEST: Sincronización BCRA USD (Fuente Confiable - API Pública)")
print("=" * 70)

# Test 1: Sincronizar rango pequeño
print("\n[TEST 1] Sincronizar rango pequeño: USD (BCRA API pública)")
print("-" * 70)
resumen = sync_bcra_historico(
    db,
    desde=date(2026, 8, 28),
    hasta=date(2026, 8, 30),
)
print(f"Recibidos: {resumen.recibidos}")
print(f"Insertados: {resumen.insertados}")
print(f"Actualizados: {resumen.actualizados}")
print(f"Sin cambios: {resumen.sin_cambios}")
print(f"Errores: {resumen.errores}")

# Test 2: Verificar última fecha
print("\n[TEST 2] Verificar última fecha USD en BD")
print("-" * 70)
ultima = obtener_ultima_fecha_bcra(db)
print(f"Última fecha USD: {ultima}")

# Test 3: Verificar registros en base de datos
print("\n[TEST 3] Verificar registros USD en BD")
print("-" * 70)
query = text("""
    SELECT COUNT(*) as total, MAX(fecha) as max_fecha, MIN(fecha) as min_fecha
    FROM tipo_cambio_hist
    WHERE moneda = 'USD' AND origen = 'OTRO' AND tipo = 'VENTA'
""")
result = db.execute(query).fetchone()
print(f"  Total registros USD: {result.total}")
print(f"  Máx fecha: {result.max_fecha}")
print(f"  Mín fecha: {result.min_fecha}")

# Test 4: Mostrar últimos registros
print("\n[TEST 4] Últimos 3 registros USD")
print("-" * 70)
query = text("""
    SELECT fecha, tipo, tasa, origen
    FROM tipo_cambio_hist
    WHERE moneda = 'USD'
    ORDER BY fecha DESC
    LIMIT 3
""")
results = db.execute(query).fetchall()
for row in results:
    print(f"  {row.fecha} | {row.tipo:8} | ${row.tasa} | {row.origen}")

db.close()

print("\n" + "=" * 70)
print("✓ Tests completados - Sincronización BCRA USD exitosa")
print("=" * 70)
print("\nNota: Solo USD (minorista) está disponible en API pública BCRA.")
print("Para mayorista, considerar: BNA, import CSV, o Flexxus ERP.")
