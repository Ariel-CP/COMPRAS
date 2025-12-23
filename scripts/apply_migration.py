"""Script sencillo para aplicar una migración SQL usando la conexión SQLAlchemy del proyecto.

Uso:
    .venv\Scripts\python.exe scripts/apply_migration.py

El script lee `database/migrations/001_add_user_session.sql` y ejecuta cada sentencia.
"""
from pathlib import Path
import sys
from sqlalchemy import text

# Asegurar que el directorio raíz del repo esté en sys.path para poder
# importar el paquete `app` cuando se ejecuta el script directamente.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import _engine


def main():
    path = Path("database/migrations/001_add_user_session.sql")
    if not path.exists():
        print(f"Archivo de migración no encontrado: {path}")
        return

    sql = path.read_text(encoding="utf-8")

    # dividir por ; y ejecutar sentencias no vacías
    statements = [s.strip() for s in sql.split(";") if s.strip()]

    with _engine.connect() as conn:
        for stmt in statements:
            try:
                conn.execute(text(stmt))
            except Exception as e:
                print("Error ejecutando sentencia:")
                print(stmt)
                raise
        # Si todo ok, confirmar (commit)
        try:
            conn.commit()
        except Exception:
            # algunos drivers/autocommit manejan commit distinto
            pass

    print("Migración aplicada (o ya existente): database/migrations/001_add_user_session.sql")


if __name__ == "__main__":
    main()
