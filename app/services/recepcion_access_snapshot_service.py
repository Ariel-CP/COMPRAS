"""Importación readonly de snapshots Access con identidad y versiones de origen."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from datetime import date, datetime
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from typing import Any, Iterator, TypedDict

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class SourceTableSpec(TypedDict):
    key: str
    parent_key: str | None


SOURCE_TABLES: dict[str, SourceTableSpec] = {
    "CONTROL DE RECEPCION": {"key": "ID_INT", "parent_key": None},
    "CRD": {"key": "Id", "parent_key": "ID_CDR"},
    "CRD-ORI": {"key": "Id", "parent_key": "ID_CDR"},
}


class AccessSnapshotError(RuntimeError):
    """Error controlado de lectura o validación del snapshot Access."""


_INSERT_VERSION_SQL = text("""
    INSERT INTO recepcion_access_source_version (
        fuente, tabla_origen, id_origen, id_padre_origen,
        contenido_hash, datos_originales, primera_corrida_id,
        ultima_corrida_id, ultima_lectura
    ) VALUES (
        :fuente, :tabla_origen, :id_origen, :id_padre_origen,
        :contenido_hash, :datos_originales, :corrida_id,
        :corrida_id, CURRENT_TIMESTAMP
    )
    ON DUPLICATE KEY UPDATE
        id_padre_origen = VALUES(id_padre_origen),
        ultima_corrida_id = VALUES(ultima_corrida_id),
        ultima_lectura = CURRENT_TIMESTAMP
    """)


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return {"__bytes_base64__": base64.b64encode(value).decode("ascii")}
    return str(value)


def preparar_version_origen(
    tabla: str, fila: dict[str, Any], *, fuente: str = "ACCESS_RECEPCION"
) -> dict[str, Any]:
    """Valida la identidad fuente y serializa una fila sin perder sus campos."""
    table_spec = SOURCE_TABLES.get(tabla)
    if table_spec is None:
        raise ValueError(
            f"La tabla Access no está habilitada para importación: {tabla}"
        )

    source_id = fila.get(table_spec["key"])
    if source_id is None or not str(source_id).strip():
        raise ValueError(f"{tabla}.{table_spec['key']} es requerido para idempotencia")

    parent_key = table_spec["parent_key"]
    parent_id = fila.get(parent_key) if parent_key else None
    payload = json.dumps(
        fila,
        sort_keys=True,
        default=_json_default,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return {
        "fuente": fuente,
        "tabla_origen": tabla,
        "id_origen": str(source_id).strip(),
        "id_padre_origen": (
            str(parent_id).strip()
            if parent_id is not None and str(parent_id).strip()
            else None
        ),
        "contenido_hash": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "datos_originales": payload,
    }


def leer_filas_access(
    path: Path, tabla: str, *, fetch_size: int
) -> Iterator[dict[str, Any]]:
    """Lee una tabla habilitada de Access mediante una conexión explícitamente readonly."""
    try:
        pyodbc = import_module("pyodbc")
    except ModuleNotFoundError as exc:
        raise AccessSnapshotError("Falta la dependencia pyodbc") from exc
    try:
        connection = pyodbc.connect(
            "Driver={Microsoft Access Driver (*.mdb, *.accdb)};"
            f"DBQ={path};Exclusive=0;ReadOnly=1;"
        )
    except pyodbc.Error as exc:
        raise AccessSnapshotError("No se pudo conectar al archivo Access") from exc
    try:
        cursor = connection.cursor()
        cursor.execute(f"SELECT * FROM [{tabla}]")
        columns = [description[0] for description in cursor.description or []]
        while rows := cursor.fetchmany(fetch_size):
            for row in rows:
                yield dict(zip(columns, row))
    except pyodbc.Error as exc:
        raise AccessSnapshotError(f"No se pudo leer la tabla Access {tabla}") from exc
    finally:
        connection.close()


def _actualizar_corrida(
    db: Session,
    corrida_id: int,
    *,
    estado: str,
    resumen: dict[str, Any],
    error: str | None = None,
) -> None:
    db.execute(
        text("""
            UPDATE recepcion_access_import_run
            SET estado = :estado,
                resumen = :resumen,
                error = :error,
                finalizado_en = CURRENT_TIMESTAMP
            WHERE id = :id
            """),
        {
            "id": corrida_id,
            "estado": estado,
            "resumen": json.dumps(resumen, ensure_ascii=False),
            "error": error,
        },
    )
    db.commit()


def importar_snapshot_access(
    db: Session,
    *,
    path: str,
    usuario_id: int,
    tablas: tuple[str, ...] = tuple(SOURCE_TABLES),
    batch_size: int = 500,
) -> dict[str, Any]:
    """Agrega snapshot Access versionado; una fila editada crea una nueva versión."""
    if batch_size < 1 or batch_size > 5000:
        raise ValueError("batch_size debe estar entre 1 y 5000")
    unknown_tables = sorted(set(tablas) - SOURCE_TABLES.keys())
    if unknown_tables:
        raise ValueError(f"Tablas Access no permitidas: {', '.join(unknown_tables)}")
    access_path = Path(path)
    if not access_path.is_file():
        raise FileNotFoundError("La base Access indicada no existe")

    run_result = db.execute(
        text("""
            INSERT INTO recepcion_access_import_run (fuente, estado, usuario_id, resumen)
            VALUES ('ACCESS_RECEPCION', 'EN_PROCESO', :usuario_id, '{}')
            """),
        {"usuario_id": usuario_id},
    )
    corrida_id = int(run_result.lastrowid)  # type: ignore[attr-defined]
    db.commit()

    resumen: dict[str, Any] = {
        "corrida_id": corrida_id,
        "tablas": {},
        "registros_leidos": 0,
    }
    try:
        for tabla in tablas:
            table_count = 0
            batch = []
            for fila in leer_filas_access(access_path, tabla, fetch_size=batch_size):
                batch.append(
                    {
                        **preparar_version_origen(tabla, fila),
                        "corrida_id": corrida_id,
                    }
                )
                table_count += 1
                if len(batch) >= batch_size:
                    db.execute(_INSERT_VERSION_SQL, batch)
                    db.commit()
                    batch.clear()
            if batch:
                db.execute(_INSERT_VERSION_SQL, batch)
                db.commit()
            resumen["tablas"][tabla] = {"registros_leidos": table_count}
            resumen["registros_leidos"] += table_count

        _actualizar_corrida(db, corrida_id, estado="COMPLETADA", resumen=resumen)
        return {**resumen, "estado": "COMPLETADA"}
    except (SQLAlchemyError, AccessSnapshotError, ValueError, OSError) as exc:
        db.rollback()
        try:
            _actualizar_corrida(
                db,
                corrida_id,
                estado="FALLIDA",
                resumen=resumen,
                error=str(exc),
            )
        except SQLAlchemyError:
            db.rollback()
            logger.exception(
                "No se pudo marcar fallida la corrida Access %s", corrida_id
            )
        raise
