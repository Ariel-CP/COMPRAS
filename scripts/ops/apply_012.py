import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlalchemy import create_engine, text

from app.core.config import get_settings

_s = get_settings()
engine = create_engine(_s.database_url, pool_pre_ping=True)

with open("database/migrations/012_sincronizacion_log.sql", encoding="utf-8") as f:
    sql = f.read()

# Filtrar bloques vacíos o que SOLO contienen comentarios
stmts = []
for block in sql.split(";"):
    lines = [
        line
        for line in block.splitlines()
        if line.strip() and not line.strip().startswith("--")
    ]
    joined = "\n".join(lines).strip()
    if joined:
        stmts.append(joined)

print(f"Sentencias a ejecutar: {len(stmts)}")
for i, s in enumerate(stmts):
    print(f"  stmt {i}: {s[:80]}")

with engine.connect() as conn:
    for s in stmts:
        conn.execute(text(s))
    conn.commit()
    result = conn.execute(text("SHOW TABLES LIKE 'sincronizacion_log'"))
    row = result.fetchone()
    print("Tabla creada:", row)
    result2 = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.tables"
            " WHERE table_schema='compras_db' AND table_name='sincronizacion_log'"
        )
    )
    print("Count info_schema:", result2.fetchone())
