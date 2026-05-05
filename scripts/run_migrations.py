"""Ejecutar migraciones 010 y 011."""
import sys
from pathlib import Path
from sqlalchemy import text, create_engine

sys.path.insert(0, '.')

from app.core.config import get_settings

settings = get_settings()
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.mysql_pool_size,
    max_overflow=settings.mysql_max_overflow,
    future=True,
)

def ejecutar_migracion(numero, ruta):
    """Ejecuta una migración SQL."""
    sql_path = Path(ruta)
    if not sql_path.exists():
        print(f"[SKIP] Archivo no encontrado: {ruta}")
        return
    
    print(f"\n{'='*60}")
    print(f"Ejecutando migracion {numero}")
    print('='*60)
    
    with open(sql_path, 'r', encoding='utf-8') as f:
        sql = f.read()
    
    try:
        with engine.begin() as conn:
            # Procesar SQL
            lines = sql.split('\n')
            sql_clean = []
            in_comment = False
            
            for line in lines:
                if '/*' in line:
                    in_comment = True
                if '*/' in line:
                    in_comment = False
                    continue
                if in_comment:
                    continue
                if line.strip().startswith('--'):
                    continue
                sql_clean.append(line)
            
            sql_cleaned = '\n'.join(sql_clean)
            statements = [s.strip() for s in sql_cleaned.split(';') 
                         if s.strip() and len(s.strip()) > 5]
            
            total = len(statements)
            print(f"Total de statements: {total}\n")
            
            for i, stmt in enumerate(statements, 1):
                preview = stmt[:70].replace('\n', ' ')
                print(f"[{i:3d}/{total}] {preview}...", end='', flush=True)
                
                try:
                    conn.execute(text(stmt))
                    print(" OK")
                except Exception as e:
                    error_str = str(e)
                    if 'already exists' in error_str or 'Duplicate' in error_str:
                        print(" (existe)")
                    else:
                        print(f"\n      ERROR: {error_str[:100]}")
            
            print(f"\n[OK] Migracion {numero} completada")
    
    except Exception as e:
        print(f"[ERROR] Fallo migracion {numero}: {e}")

# Ejecutar
migraciones = [
    ('010', 'database/migrations/010_recepcion_y_evaluacion_tablas.sql'),
    ('011', 'database/migrations/011_recepcion_tablas_restantes.sql'),
]

for numero, ruta in migraciones:
    ejecutar_migracion(numero, ruta)

print(f"\n{'='*60}")
print("TODAS LAS MIGRACIONES COMPLETADAS")
print('='*60)
