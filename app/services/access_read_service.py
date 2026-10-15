"""Lectura diagnóstica de Microsoft Access en modo exclusivamente lectura."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

ALLOWED_TABLES = frozenset({"CONTROL DE RECEPCION", "Listado Planos"})


class AccessReadError(RuntimeError):
    """Error controlado al acceder a la base Access."""


def _validate_table_name(table_name: str) -> str:
    normalized = (table_name or "").strip()
    if normalized not in ALLOWED_TABLES:
        raise AccessReadError("La tabla Access solicitada no está permitida")
    return normalized


def inspect_access_table(
    *,
    path: str | None = None,
    table_name: str | None = None,
    sample_limit: int = 10,
) -> dict[str, Any]:
    """Devuelve metadatos y una muestra de Access sin modificarla."""
    settings = get_settings()
    database_path = path or settings.access_db_path
    if not database_path:
        raise AccessReadError("ACCESS_DB_PATH no está configurado")

    file_path = Path(database_path)
    if not file_path.is_file():
        raise FileNotFoundError("La base Access configurada no existe")

    table = _validate_table_name(table_name or settings.access_table_name)
    limit = max(1, min(int(sample_limit), 100))

    try:
        import pyodbc  # type: ignore[import-untyped]
    except ModuleNotFoundError as exc:
        raise AccessReadError("Falta la dependencia pyodbc") from exc

    connection_string = (
        "Driver={Microsoft Access Driver (*.mdb, *.accdb)};"
        f"DBQ={file_path};"
        "Exclusive=0;"
        "ReadOnly=1;"
    )

    connection = None
    try:
        connection = pyodbc.connect(connection_string)
        cursor = connection.cursor()
        cursor.execute(f"SELECT TOP {limit} * FROM [{table}]")
        columns = [description[0] for description in cursor.description or []]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return {
            "archivo": str(file_path),
            "tabla": table,
            "columnas": columns,
            "muestra": rows,
            "limite_muestra": limit,
        }
    except AccessReadError:
        raise
    except Exception as exc:
        logger.exception("Error leyendo Access en modo diagnóstico")
        raise AccessReadError("No se pudo consultar la base Access") from exc
    finally:
        if connection is not None:
            connection.close()


def inspect_access_schema(*, path: str | None = None) -> dict[str, Any]:
    """Devuelve tablas visibles y columnas relevantes de Access."""
    settings = get_settings()
    database_path = path or settings.access_db_path
    if not database_path:
        raise AccessReadError("ACCESS_DB_PATH no está configurado")

    file_path = Path(database_path)
    if not file_path.is_file():
        raise FileNotFoundError("La base Access configurada no existe")

    try:
        import pyodbc  # type: ignore[import-untyped]
    except ModuleNotFoundError as exc:
        raise AccessReadError("Falta la dependencia pyodbc") from exc

    connection_string = (
        "Driver={Microsoft Access Driver (*.mdb, *.accdb)};"
        f"DBQ={file_path};"
        "Exclusive=0;"
        "ReadOnly=1;"
    )

    connection = None
    try:
        connection = pyodbc.connect(connection_string)
        cursor = connection.cursor()
        visible_tables = sorted(
            row.table_name
            for row in cursor.tables(tableType="TABLE")
            if row.table_name
        )
        tables: dict[str, list[dict[str, Any]]] = {}
        for table_name in sorted(ALLOWED_TABLES):
            columns = []
            for row in cursor.columns(table=table_name):
                columns.append(
                    {
                        "nombre": getattr(row, "column_name", None),
                        "tipo": getattr(row, "type_name", None),
                        "tamano": getattr(row, "column_size", None),
                        "permite_nulo": getattr(row, "nullable", None),
                    }
                )
            if columns:
                tables[table_name] = columns

        return {
            "archivo": str(file_path),
            "tablas_visibles": visible_tables,
            "tablas_relevantes": tables,
        }
    except Exception as exc:
        logger.exception("Error inspeccionando el esquema Access")
        raise AccessReadError("No se pudo inspeccionar el esquema Access") from exc
    finally:
        if connection is not None:
            connection.close()