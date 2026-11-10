"""Aplica un archivo de migración SQL usando la conexión SQLAlchemy del proyecto.

Uso:
    .venv\Scripts\python.exe scripts/ops/apply_migration.py database/migrations/021_recepcion_inspeccion_intentos.sql

Si no se especifica una ruta, conserva el destino histórico 001_add_user_session.sql.
"""
from pathlib import Path
import sys
from sqlalchemy import text

# Asegurar que el directorio raíz del repo esté en sys.path para poder
# importar el paquete `app` cuando se ejecuta el script directamente.
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import _engine  # noqa: E402


def main():
    migration_path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "database/migrations/001_add_user_session.sql"
    )
    path = Path(migration_path)
    if not path.is_absolute():
        path = ROOT_DIR / path
    if not path.exists():
        print(f"Archivo de migración no encontrado: {path}")
        raise SystemExit(1)

    sql = path.read_text(encoding="utf-8")

    # dividir por ; y ejecutar sentencias no vacías
    statements = [s.strip() for s in sql.split(";") if s.strip()]

    with _engine.connect() as conn:
        for stmt in statements:
            try:
                conn.execute(text(stmt))
            except Exception as exc:
                print("Error ejecutando sentencia:")
                print(stmt)
                print(exc)
                raise
        # Si todo ok, confirmar (commit)
        try:
            conn.commit()
        except RuntimeError:
            # algunos drivers/autocommit manejan commit distinto
            pass

    print(f"Migración aplicada: {path.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
