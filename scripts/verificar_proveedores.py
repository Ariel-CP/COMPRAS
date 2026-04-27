#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from app.db import SessionLocal
from sqlalchemy import text

db = SessionLocal()
rows = db.execute(text("SELECT id, codigo, nombre, cuit, localidad, provincia FROM proveedor WHERE codigo LIKE 'TEST%'")).fetchall()
print(f'Proveedores insertados: {len(rows)}')
for row in rows:
    print(f'  ID={row[0]}, Código={row[1]}, Nombre={row[2]}, CUIT={row[3]}, Localidad={row[4]}, Provincia={row[5]}')
db.close()
