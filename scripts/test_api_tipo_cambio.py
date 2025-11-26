"""Test endpoint API tipo_cambio."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import _engine
from app.schemas.tipo_cambio import TipoCambioFiltro
from app.services.tipo_cambio_service import listar_tipos_cambio

filtro = TipoCambioFiltro(moneda=None, tipo=None, desde=None, hasta=None)

with _engine.connect() as conn:
    resultado = listar_tipos_cambio(conn, filtro)
    print(f"Total registros: {len(resultado)}")
    if resultado:
        print("\nPrimeros 3 registros:")
        import json
        for r in resultado[:3]:
            print(json.dumps(r, indent=2, ensure_ascii=False))
