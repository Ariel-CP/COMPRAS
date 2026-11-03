#!/usr/bin/env python3
"""Check tipo_cambio data in DB."""
import sys
sys.path.insert(0, '.')

from app.db import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    # Contar registros
    result = db.execute(text("SELECT COUNT(*) as cnt FROM tipo_cambio_hist WHERE moneda='USD'"))
    count = result.fetchone()[0]
    print(f"Total USD records in DB: {count}")
    
    # Ver últimos 5
    result = db.execute(text("""
        SELECT fecha, moneda, tipo, tasa, origen 
        FROM tipo_cambio_hist 
        WHERE moneda='USD' 
        ORDER BY fecha DESC 
        LIMIT 5
    """))
    print("\nLatest USD records:")
    for row in result:
        print(f"  {row[0]} {row[1]} {row[2]}: {row[3]} (origen: {row[4]})")
finally:
    db.close()
