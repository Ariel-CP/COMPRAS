from app.db import SessionLocal
from sqlalchemy import inspect

db = SessionLocal()
inspector = inspect(db.get_bind())

# Obtener columnas de la tabla tipo_cambio_hist
columns = inspector.get_columns('tipo_cambio_hist')
print("Columnas de tipo_cambio_hist:")
for col in columns:
    print(f"  {col['name']} ({col['type']})")

db.close()
