import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.db import SessionLocal  # noqa: E402
from sqlalchemy import text  # noqa: E402


def main():
    db = SessionLocal()
    try:
        rows = db.execute(text('SELECT id,nombre,descripcion FROM rol ORDER BY id')).fetchall()
        print('FOUND', len(rows))
        for r in rows:
            print(r[0], r[1], r[2])
    finally:
        db.close()


if __name__ == '__main__':
    main()
