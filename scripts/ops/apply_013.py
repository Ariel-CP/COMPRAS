import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlalchemy import create_engine, text
from app.core.config import get_settings

_s = get_settings()
engine = create_engine(_s.database_url, pool_pre_ping=True)

with open("database/migrations/013_evaluacion_proveedor_anual.sql", encoding="utf-8") as f:
    sql = f.read()

# Separar en sentencias individuales ignorando líneas de comentario
stmts = []
for block in sql.split(";"):
    lines = [l for l in block.splitlines() if l.strip() and not l.strip().startswith("--")]
    joined = "\n".join(lines).strip()
    if joined:
        stmts.append(joined)

print(f"Sentencias a ejecutar: {len(stmts)}")
with engine.connect() as conn:
    for i, s in enumerate(stmts):
        print(f"  [{i+1}] {s[:70]}…")
        conn.execute(text(s))
    conn.commit()

# Verificar
with engine.connect() as conn:
    for tabla in ("evaluacion_proveedor_anual", "evaluacion_criterio_detalle"):
        r = conn.execute(text(f"SHOW TABLES LIKE '{tabla}'")).fetchone()
        print(f"  Tabla {tabla}: {'OK' if r else 'FALTA'}")
    # Verificar columnas nuevas en proveedor
    r = conn.execute(text("SHOW COLUMNS FROM proveedor LIKE 'clasificacion'")).fetchone()
    print(f"  Col proveedor.clasificacion: {'OK' if r else 'FALTA'}")
    r = conn.execute(text("SHOW COLUMNS FROM proveedor LIKE 'estado_calificacion'")).fetchone()
    print(f"  Col proveedor.estado_calificacion: {'OK' if r else 'FALTA'}")
