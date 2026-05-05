"""Verificar tablas existentes y estructura."""
import sys
sys.path.insert(0, '.')

from sqlalchemy import create_engine, inspect
from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, future=True)

with engine.connect() as conn:
    inspector = inspect(engine)
    
    # Verificar tablas clave
    tablas = ['proveedor', 'producto', 'usuario', 'unidad_medida', 'parametro_sistema']
    
    for tabla in tablas:
        if tabla in inspector.get_table_names():
            print(f'\n[OK] Tabla {tabla} existe')
            cols = inspector.get_columns(tabla)
            print(f'  Columnas: {len(cols)}')
            for col in cols[:5]:
                print(f'    - {col["name"]}: {col["type"]}')
        else:
            print(f'\n[FALTA] Tabla {tabla} NO existe')
            
    # Mostrar todas las tablas
    print(f'\n\nTodas las tablas en BD:')
    all_tables = inspector.get_table_names()
    for t in sorted(all_tables):
        print(f'  - {t}')
