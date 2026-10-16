"""Lectura diagnóstica de Microsoft Access en modo exclusivamente lectura."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from importlib import import_module
from pathlib import Path
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

ALLOWED_TABLES = frozenset({"CONTROL DE RECEPCION", "Listado Planos"})
HISTORIC_RECEIPTION_COLUMNS = (
    "ID_INT",
    "PLANO",
    "PROVEEDOR",
    "FECHA EMISION OC",
    "CANTIDAD OC",
    "Remito",
    "N_interno",
    "Fecha de Entrega",
    "Recibio",
    "Lote",
    "MUESTREO",
    "PORCENTAJE TOTAL",
    "Material",
    "Fecha Control",
    "Estado",
    "NOTA",
    "PLAN MUESTREO",
    "CONTROL DIMENSIONAL",
    "TERMINACION SUPERFICIAL",
    "EMBALAJE",
    "Controlo",
    "Codigo Proveedor",
    "TieneCertificado",
    "ORDEN DE COMPRA",
)
RECENT_RECEIPTION_COLUMNS = (
    "ID_INT",
    "N_interno",
    "Fecha Control",
    "PLANO",
    "PROVEEDOR",
    "Material",
    "ORDEN DE COMPRA",
    "Remito",
    "Estado",
)
HISTORIC_INSPECTION_COLUMNS = (
    "Id",
    "ID_CDR",
    "CONTROL",
    "COTA",
    "DESVIACION",
    "ACEPTADO",
)


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
        pyodbc = import_module("pyodbc")
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
    """Devuelve inventario de tablas, columnas, PK y FK visibles en Access."""
    settings = get_settings()
    database_path = path or settings.access_db_path
    if not database_path:
        raise AccessReadError("ACCESS_DB_PATH no está configurado")

    file_path = Path(database_path)
    if not file_path.is_file():
        raise FileNotFoundError("La base Access configurada no existe")

    try:
        pyodbc = import_module("pyodbc")
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
        table_objects = [
            row
            for row in cursor.tables()
            if getattr(row, "table_name", None)
            and str(getattr(row, "table_type", "")).upper()
            in {"TABLE", "VIEW", "SYNONYM"}
        ]
        table_objects.sort(key=lambda row: row.table_name)
        visible_tables = [row.table_name for row in table_objects]
        table_types = {
            row.table_name: str(getattr(row, "table_type", "UNKNOWN")).upper()
            for row in table_objects
        }
        inventory: dict[str, dict[str, Any]] = {}
        metadata_warnings = []
        reported_metadata_warnings = set()

        def record_metadata_warning(table_name: str, metadata_name: str) -> None:
            if metadata_name in reported_metadata_warnings:
                return
            reported_metadata_warnings.add(metadata_name)
            metadata_warnings.append(
                {
                    "metadato": metadata_name,
                    "mensaje": "No se pudo consultar este metadato con el driver/objeto ODBC.",
                }
            )
            logger.warning(
                "No se pudo consultar el metadato ODBC %s (ejemplo de objeto: %s)",
                metadata_name,
                table_name,
            )

        for table_name in visible_tables:
            columns = [
                {
                    "nombre": getattr(row, "column_name", None),
                    "tipo": getattr(row, "type_name", None),
                    "tamano": getattr(row, "column_size", None),
                    "permite_nulo": getattr(row, "nullable", None),
                    "ordinal": getattr(row, "ordinal_position", None),
                }
                for row in cursor.columns(table=table_name)
            ]
            unavailable_metadata = []
            try:
                primary_key_rows = list(cursor.primaryKeys(table=table_name))
            except (pyodbc.Error, AttributeError):
                primary_key_rows = None
                unavailable_metadata.append("clave_primaria")
                record_metadata_warning(table_name, "clave_primaria")
            primary_keys = sorted(
                [
                    {
                        "nombre": getattr(row, "column_name", None),
                        "orden": getattr(row, "key_seq", None),
                        "restriccion": getattr(row, "pk_name", None),
                    }
                    for row in (primary_key_rows or [])
                ],
                key=lambda item: item["orden"] or 0,
            )
            try:
                foreign_key_rows = list(cursor.foreignKeys(foreignTable=table_name))
            except (pyodbc.Error, AttributeError):
                foreign_key_rows = None
                unavailable_metadata.append("claves_foraneas")
                record_metadata_warning(table_name, "claves_foraneas")
            foreign_keys = [
                {
                    "tabla_referenciada": getattr(row, "pktable_name", None),
                    "columna_referenciada": getattr(row, "pkcolumn_name", None),
                    "columna_local": getattr(row, "fkcolumn_name", None),
                    "orden": getattr(row, "key_seq", None),
                    "restriccion": getattr(row, "fk_name", None),
                }
                for row in (foreign_key_rows or [])
            ]
            inventory[table_name] = {
                "tipo_objeto": table_types[table_name],
                "columnas": columns,
                "clave_primaria": primary_keys,
                "claves_foraneas": foreign_keys,
                "metadatos_no_disponibles": unavailable_metadata,
            }

        return {
            "archivo": str(file_path),
            "tablas_visibles": visible_tables,
            "inventario": inventory,
            "advertencias": metadata_warnings,
            # Mantener compatibilidad con clientes previos de este endpoint.
            "tablas_relevantes": {
                name: inventory[name]["columnas"]
                for name in sorted(ALLOWED_TABLES.intersection(inventory))
            },
        }
    except Exception as exc:
        logger.exception("Error inspeccionando el esquema Access")
        raise AccessReadError("No se pudo inspeccionar el esquema Access") from exc
    finally:
        if connection is not None:
            connection.close()


def _access_read_connection(path: str | None = None):
    settings = get_settings()
    database_path = path or settings.access_db_path
    if not database_path:
        raise AccessReadError("ACCESS_DB_PATH no está configurado")
    file_path = Path(database_path)
    if not file_path.is_file():
        raise FileNotFoundError("La base Access configurada no existe")
    try:
        pyodbc = import_module("pyodbc")
    except ModuleNotFoundError as exc:
        raise AccessReadError("Falta la dependencia pyodbc") from exc
    connection_string = (
        "Driver={Microsoft Access Driver (*.mdb, *.accdb)};"
        f"DBQ={file_path};Exclusive=0;ReadOnly=1;"
    )
    try:
        return pyodbc.connect(connection_string)
    except pyodbc.Error as exc:
        raise AccessReadError("No se pudo conectar a la base Access") from exc


def listar_controles_access(
    *,
    q: str | None = None,
    proveedor_codigo: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    before_id: int | None = None,
    limit: int = 50,
    path: str | None = None,
) -> list[dict[str, Any]]:
    """Lista recepciones históricas de Access en orden ID_INT descendente."""
    safe_limit = max(1, min(int(limit), 100))
    if desde and hasta and desde > hasta:
        raise ValueError("La fecha Desde no puede ser posterior a la fecha Hasta")

    columns = ", ".join(f"[{column}]" for column in HISTORIC_RECEIPTION_COLUMNS)
    where: list[str] = []
    params: list[Any] = []
    if before_id is not None:
        where.append("[ID_INT] < ?")
        params.append(int(before_id))
    if desde is not None:
        where.append("[Fecha Control] >= ?")
        params.append(desde)
    if hasta is not None:
        where.append("[Fecha Control] < ?")
        params.append(hasta + timedelta(days=1))
    if proveedor_codigo and proveedor_codigo.strip():
        where.append("[Codigo Proveedor] = ?")
        params.append(proveedor_codigo.strip())
    if q and q.strip():
        where.append(
            "([Codigo Proveedor] LIKE ? OR [Material] LIKE ? OR [PROVEEDOR] LIKE ? "
            "OR [ORDEN DE COMPRA] LIKE ? OR [Remito] LIKE ? OR [NOTA] LIKE ? "
            "OR ([PLANO] & '') LIKE ? OR ([N_interno] & '') LIKE ? "
            "OR ([ID_INT] & '') LIKE ?)"
        )
        pattern = f"%{q.strip()}%"
        params.extend([pattern] * 9)

    where_sql = f" WHERE {' AND '.join(where)}" if where else ""
    query = (
        f"SELECT TOP {safe_limit} {columns} FROM [CONTROL DE RECEPCION]"
        f"{where_sql} ORDER BY [ID_INT] DESC"
    )
    connection = _access_read_connection(path)
    try:
        cursor = connection.cursor()
        cursor.execute(query, params)
        names = [description[0] for description in cursor.description or []]
        return [dict(zip(names, row)) for row in cursor.fetchall()]
    except Exception as exc:
        logger.exception("Error consultando histórico de controles Access")
        raise AccessReadError("No se pudo consultar el historial de Access") from exc
    finally:
        connection.close()


def listar_recepciones_recientes_access(
    *,
    q: str | None = None,
    proveedor_codigo: str | None = None,
    limit: int = 100,
    path: str | None = None,
) -> list[dict[str, Any]]:
    """Lista el resumen reciente desde la misma tabla fuente del historial Access."""
    safe_limit = max(1, min(int(limit), 100))
    columns = ", ".join(f"[{column}]" for column in RECENT_RECEIPTION_COLUMNS)
    params: list[Any] = []
    where = []
    if proveedor_codigo and proveedor_codigo.strip():
        where.append("[Codigo Proveedor] = ?")
        params.append(proveedor_codigo.strip())
    if q and q.strip():
        where.append(
            "([Codigo Proveedor] LIKE ? OR [PROVEEDOR] LIKE ? OR [Material] LIKE ? "
            "OR [ORDEN DE COMPRA] LIKE ? OR [Remito] LIKE ? "
            "OR ([PLANO] & '') LIKE ? OR ([ID_INT] & '') LIKE ? "
            "OR ([N_interno] & '') LIKE ?)"
        )
        pattern = f"%{q.strip()}%"
        params.extend([pattern] * 8)
    where_sql = f" WHERE {' AND '.join(where)}" if where else ""
    query = (
        f"SELECT TOP {safe_limit} {columns} FROM [CONTROL DE RECEPCION]"
        f"{where_sql} ORDER BY [ID_INT] DESC"
    )
    connection = _access_read_connection(path)
    try:
        cursor = connection.cursor()
        cursor.execute(query, params)
        names = [description[0] for description in cursor.description or []]
        return [dict(zip(names, row)) for row in cursor.fetchall()]
    except Exception as exc:
        logger.exception("Error consultando recepciones recientes de Access")
        raise AccessReadError("No se pudieron consultar las recepciones de Access") from exc
    finally:
        connection.close()


def obtener_control_access(
    access_id: int, *, path: str | None = None
) -> dict[str, Any] | None:
    """Devuelve la recepción histórica y sus cotas enlazadas por CRD.ID_CDR."""
    columns = ", ".join(f"[{column}]" for column in HISTORIC_RECEIPTION_COLUMNS)
    connection = _access_read_connection(path)
    try:
        cursor = connection.cursor()
        cursor.execute(
            f"SELECT {columns} FROM [CONTROL DE RECEPCION] WHERE [ID_INT] = ?",
            [int(access_id)],
        )
        names = [description[0] for description in cursor.description or []]
        row = cursor.fetchone()
        if row is None:
            return None
        receipt = dict(zip(names, row))

        cursor.execute(
            "SELECT [Id], [ID_CDR], [CONTROL], [COTA], [DESVIACION], [ACEPTADO] "
            "FROM [CRD] WHERE [ID_CDR] = ? ORDER BY [Id]",
            [int(access_id)],
        )
        inspection_names = [description[0] for description in cursor.description or []]
        receipt["controles"] = [
            dict(zip(inspection_names, inspection)) for inspection in cursor.fetchall()
        ]
        return receipt
    except Exception as exc:
        logger.exception("Error consultando detalle histórico Access ID_INT=%s", access_id)
        raise AccessReadError("No se pudo consultar el detalle del control Access") from exc
    finally:
        connection.close()
