"""Test endpoint tipo_cambio."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import _engine
from sqlalchemy import text

with _engine.connect() as conn:
    result = conn.execute(text("SELECT * FROM tipo_cambio_hist LIMIT 3"))
    print("Estructura de datos retornados:")
    for r in result:
        data = dict(r._mapping)
        print(f"\nRegistro: {data}")
        for k, v in data.items():
            print(f"  {k}: {v} (tipo: {type(v).__name__})")
