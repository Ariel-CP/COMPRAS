"""Enriquece staging desde Access sin sobrescribir valores existentes.

Uso:
    .venv\\Scripts\\python.exe scripts\\ops\\enriquecer_recepcion_staging.py
    .venv\\Scripts\\python.exe scripts\\ops\\enriquecer_recepcion_staging.py --apply
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.services.recepcion_sync_service import (  # noqa: E402
    _generar_hash_fila,
    leer_tabla_access,
    mapear_fila_a_staging,
)

logger = logging.getLogger(__name__)

UPSERT_SQL = text("""
    INSERT INTO recepcion_staging (
        fuente, fila_hash, usuario_importacion_id, id_recepcion_original,
        proveedor_codigo, proveedor_nombre, producto_codigo, producto_nombre,
        cantidad_solicitada, cantidad_recibida, lote_numero, fecha_vencimiento,
        fecha_recepcion_original, estado_inspeccion_original, calidad_ok,
        codigo_no_conformidad, descripcion_no_conformidad, notas_adicionales,
        inspector_nombre, estado_procesamiento
    ) VALUES (
        'ACCESS_CONTROL_RECEPCION', :fila_hash, :usuario_importacion_id,
        :id_recepcion_original, :proveedor_codigo, :proveedor_nombre,
        :producto_codigo, :producto_nombre, :cantidad_solicitada,
        :cantidad_recibida, :lote_numero, :fecha_vencimiento,
        :fecha_recepcion_original, :estado_inspeccion_original, :calidad_ok,
        :codigo_no_conformidad, :descripcion_no_conformidad,
        :notas_adicionales, :inspector_nombre, 'PENDIENTE'
    )
    ON DUPLICATE KEY UPDATE
        id_recepcion_original = COALESCE(
            id_recepcion_original, VALUES(id_recepcion_original)
        ),
        proveedor_codigo = COALESCE(proveedor_codigo, VALUES(proveedor_codigo)),
        fecha_recepcion_original = COALESCE(
            fecha_recepcion_original, VALUES(fecha_recepcion_original)
        ),
        estado_inspeccion_original = COALESCE(
            estado_inspeccion_original, VALUES(estado_inspeccion_original)
        ),
        lote_numero = COALESCE(lote_numero, VALUES(lote_numero))
""")


def preparar_filas(filas_access: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filas: list[dict[str, Any]] = []
    hashes: set[str] = set()
    for fila_access in filas_access:
        fila_hash = _generar_hash_fila(fila_access)
        if fila_hash in hashes:
            raise ValueError("Access devolvió filas repetidas con el mismo hash")
        hashes.add(fila_hash)
        fila = mapear_fila_a_staging(fila_access)
        fila.update(
            fila_hash=fila_hash,
            usuario_importacion_id=1,
        )
        filas.append(fila)
    return filas


def cargar(*, aplicar: bool, batch_size: int = 100) -> dict[str, int | bool]:
    settings = get_settings()
    if not settings.access_db_path:
        raise ValueError("ACCESS_DB_PATH no está configurado")

    filas = preparar_filas(leer_tabla_access(settings.access_db_path))
    if not filas:
        raise ValueError("Access no devolvió registros; se cancela la carga")

    db = SessionLocal()
    try:
        hashes_existentes = {
            str(row[0])
            for row in db.execute(text("SELECT fila_hash FROM recepcion_staging")).all()
        }
        hashes_origen = {str(fila["fila_hash"]) for fila in filas}
        coincidencias = hashes_existentes & hashes_origen
        nuevas = hashes_origen - hashes_existentes

        resultado: dict[str, int | bool] = {
            "aplicada": aplicar,
            "filas_access": len(filas),
            "hashes_coincidentes": len(coincidencias),
            "campos_existentes_a_completar": len(coincidencias),
            "filas_nuevas_estimadas": len(nuevas),
            "filas_staging_antes": len(hashes_existentes),
        }
        if not aplicar:
            return resultado

        aplicadas = 0
        for inicio in range(0, len(filas), batch_size):
            lote = filas[inicio : inicio + batch_size]
            try:
                db.execute(UPSERT_SQL, lote)
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                logger.exception(
                    "Falló el lote %d-%d; los lotes anteriores quedaron confirmados",
                    inicio + 1,
                    inicio + len(lote),
                )
                raise
            aplicadas += len(lote)

        total_despues = int(
            db.execute(text("SELECT COUNT(*) FROM recepcion_staging")).scalar_one()
        )
        resultado.update(
            filas_procesadas=aplicadas,
            filas_staging_despues=total_despues,
        )
        return resultado
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica el enriquecimiento idempotente; por defecto solo simula.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        choices=range(10, 501),
        metavar="10..500",
        help="Filas por transacción corta (predeterminado: 100).",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        print(cargar(aplicar=args.apply, batch_size=args.batch_size))
    except (OSError, ValueError, SQLAlchemyError):
        logger.exception("Carga de historial Access abortada")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
