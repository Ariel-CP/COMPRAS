"""
Script de migración: Ejecutar 010_recepcion_y_evaluacion_tablas.sql
"""

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

# Ejecutar ambas migraciones en secuencia
migraciones = [
    ('010', 'database/migrations/010_recepcion_y_evaluacion_tablas.sql'),
    ('011', 'database/migrations/011_recepcion_tablas_restantes.sql'),
]

for numero, ruta in migraciones:
    print(f"\n{'='*60}")
    print(f"Ejecutando migración {numero}: {ruta}")
    print('='*60)
    
    sql_path = Path(ruta)
    if not sql_path.exists():
        print(f"[SKIP] Archivo no encontrado: {ruta}")
        continue
    
    with open(sql_path, 'r', encoding='utf-8') as f:
        sql = f.read()

try:
    with engine.begin() as conn:
        # Leer y procesar SQL línea por línea para manejar comentarios
        lines = sql.split('\n')
        sql_clean = []
        in_comment = False
        
        for line in lines:
            # Ignorar comentarios de multilínea
            if '/*' in line:
                in_comment = True
            if '*/' in line:
                in_comment = False
                continue
            
            if in_comment:
                continue
            
            # Ignorar comentarios de línea
            if line.strip().startswith('--'):
                continue
            
            sql_clean.append(line)
        
        sql_cleaned = '\n'.join(sql_clean)
        
        # Separar por ; pero preservar líneas en blanco
        statements = [s.strip() for s in sql_cleaned.split(';') 
                     if s.strip() and len(s.strip()) > 5]
        
        total = len(statements)
        print(f"Total de statements encontrados: {total}\n")
        
        if total == 0:
            print("No se encontraron statements para ejecutar")
            print("\nPrimeras líneas del SQL:")
            print('\n'.join(sql.split('\n')[:10]))
            sys.exit(1)
        
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
        
        print("\n[OK] Migracion completada exitosamente")

except Exception as e:
    print(f"[ERROR] Fatal: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
