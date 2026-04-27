#!/usr/bin/env python3
"""Script para ejecutar migración de campos proveedor"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text, create_engine
from app.core.config import get_settings

def aplicar_migracion():
    """Aplica migración SQL para agregar campos a tabla proveedor"""
    
    settings = get_settings()
    engine = create_engine(settings.database_url)
    
    sql_file = project_root / "database" / "agregar_campos_proveedor.sql"
    sql_script = sql_file.read_text(encoding='utf-8')
    
    # Remover comentarios de bloque /* ... */
    import re
    sql_script = re.sub(r'/\*.*?\*/', '', sql_script, flags=re.DOTALL)
    
    # Remover comentarios de línea --
    lines = []
    for line in sql_script.split('\n'):
        if '--' in line:
            line = line[:line.index('--')]
        lines.append(line)
    sql_script = '\n'.join(lines)
    
    # Dividir por sentencias (por ;)
    sentencias = [s.strip() for s in sql_script.split(';') if s.strip()]
    
    with engine.connect() as conn:
        for sentencia in sentencias:
            try:
                print(f"Ejecutando: {sentencia[:60]}...")
                conn.execute(text(sentencia))
                conn.commit()
                print("✅ OK")
            except Exception as e:
                if "already exists" in str(e) or "Duplicate" in str(e):
                    print(f"⚠️ Campo/Índice ya existe: {e}")
                else:
                    print(f"❌ Error: {e}")
                    conn.rollback()
                    raise

if __name__ == "__main__":
    print("Aplicando migración de campos proveedor...")
    aplicar_migracion()
    print("\n✅ Migración completada exitosamente")
