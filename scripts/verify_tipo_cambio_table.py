"""Script para verificar la estructura de la tabla tipo_cambio_hist."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.db import _engine


def main():
    with _engine.connect() as conn:
        result = conn.execute(text("DESCRIBE tipo_cambio_hist"))
        print("Estructura de la tabla tipo_cambio_hist:")
        print("-" * 80)
        print(f"{'Campo':<20} {'Tipo':<30} {'Nulo':<10} {'Clave':<10}")
        print("-" * 80)
        for row in result:
            print(f"{row[0]:<20} {row[1]:<30} {row[2]:<10} {row[3]:<10}")


if __name__ == "__main__":
    main()
