"""Script para crear la tabla tipo_cambio_hist en la base de datos."""
import sys
from pathlib import Path

# Agregar directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.db import _engine

SQL_CREATE_TABLE = """
DROP TABLE IF EXISTS tipo_cambio_hist;

CREATE TABLE tipo_cambio_hist (
  id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  fecha date NOT NULL,
  moneda enum('ARS','USD','USD_MAY','EUR') NOT NULL,
  tipo enum('COMPRA','VENTA','PROMEDIO') NOT NULL DEFAULT 'PROMEDIO',
  tasa decimal(18,6) NOT NULL,
  origen enum('ERP_FLEXXUS','MANUAL','OTRO') NOT NULL DEFAULT 'MANUAL',
  notas varchar(255) DEFAULT NULL,
  fecha_creacion timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (id),
  UNIQUE KEY uk_tc_moneda_fecha_tipo (moneda,fecha,tipo),
  KEY ix_tc_moneda_fecha (moneda,fecha),
  CONSTRAINT chk_tc_tasa CHECK (tasa > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

def main():
    with _engine.begin() as conn:
        # Ejecutar DROP
        conn.execute(text("DROP TABLE IF EXISTS tipo_cambio_hist"))
        print("✓ Tabla tipo_cambio_hist eliminada (si existía)")
        
        # Ejecutar CREATE
        create_sql = """
        CREATE TABLE tipo_cambio_hist (
          id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
          fecha date NOT NULL,
          moneda enum('ARS','USD','USD_MAY','EUR') NOT NULL,
          tipo enum('COMPRA','VENTA','PROMEDIO') NOT NULL DEFAULT 'PROMEDIO',
          tasa decimal(18,6) NOT NULL,
          origen enum('ERP_FLEXXUS','MANUAL','OTRO') NOT NULL DEFAULT 'MANUAL',
          notas varchar(255) DEFAULT NULL,
          fecha_creacion timestamp NOT NULL DEFAULT current_timestamp(),
          PRIMARY KEY (id),
          UNIQUE KEY uk_tc_moneda_fecha_tipo (moneda,fecha,tipo),
          KEY ix_tc_moneda_fecha (moneda,fecha),
          CONSTRAINT chk_tc_tasa CHECK (tasa > 0)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
        conn.execute(text(create_sql))
        print("✓ Tabla tipo_cambio_hist creada exitosamente")
        
        # Verificar
        result = conn.execute(text("SHOW TABLES LIKE 'tipo_cambio_hist'"))
        if result.fetchone():
            print("✓ Verificación: Tabla existe en la base de datos")
        else:
            print("✗ Error: La tabla no se encontró después de crearla")

if __name__ == "__main__":
    main()
