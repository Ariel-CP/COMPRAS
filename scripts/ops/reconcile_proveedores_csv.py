"""Reconcilia el maestro de proveedores desde el CSV de Flexxus.

Por defecto solo informa. Requiere --apply para escribir en la base configurada.
Los proveedores ausentes quedan inactivos, no se borran, para preservar su
identidad y las evaluaciones históricas asociadas. Ejecutar como módulo desde
la raíz del repositorio: python -m scripts.ops.reconcile_proveedores_csv.
"""

from __future__ import annotations

import argparse
import csv
import io
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import bindparam, create_engine, text

from app.core.config import get_settings
from app.services.proveedor_import_service import (
    COLUMN_ALIASES,
    _normalize_column_name,
    _validate_cuit,
)

logger = logging.getLogger("reconcile_proveedores")

UPSERT = text(
    """
    INSERT INTO proveedor (
        codigo, nombre, cuit, direccion, telefono, localidad, provincia, email, activo
    ) VALUES (
        :codigo, :nombre, :cuit, :direccion, :telefono, :localidad, :provincia,
        :email, :activo
    )
    ON DUPLICATE KEY UPDATE
        nombre = VALUES(nombre),
        cuit = VALUES(cuit),
        direccion = VALUES(direccion),
        telefono = VALUES(telefono),
        localidad = VALUES(localidad),
        provincia = VALUES(provincia),
        email = VALUES(email),
        activo = VALUES(activo),
        fecha_actualizacion = CURRENT_TIMESTAMP
    """
)


def _clean_cell(value: str) -> str:
    value = value.strip()
    if value.startswith('="') and value.endswith('"'):
        value = value[2:-1].replace('""', '"')
    return value.strip()


def load_source(path: Path) -> list[dict[str, Any]]:
    content = path.read_bytes().decode("cp1252")
    reader = csv.reader(io.StringIO(content, newline=""), delimiter=";")
    try:
        headers = next(reader)
    except StopIteration as exc:
        raise ValueError("El CSV está vacío") from exc

    field_map: dict[int, str] = {}
    for index, header in enumerate(headers):
        key = _normalize_column_name(header)
        canonical = COLUMN_ALIASES.get(key, key)
        if canonical in {
            "codigo", "nombre", "cuit", "direccion", "telefono",
            "localidad", "provincia", "email",
        }:
            if canonical in field_map.values():
                raise ValueError(f"Columna duplicada para {canonical}")
            field_map[index] = canonical

    required = {"codigo", "nombre"}
    found = set(field_map.values())
    if not required.issubset(found):
        raise ValueError("El CSV debe incluir Código y Razón Social")

    records: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    for line_number, row in enumerate(reader, start=2):
        if not any(value.strip() for value in row):
            continue
        if len(row) != len(headers):
            raise ValueError(f"Fila {line_number}: cantidad de columnas inesperada")

        values = {
            canonical: _clean_cell(row[index])
            for index, canonical in field_map.items()
        }
        code = values.get("codigo", "")
        name = values.get("nombre", "")
        if not code or not name:
            raise ValueError(f"Fila {line_number}: falta código o razón social")
        if code in seen_codes:
            raise ValueError(f"Fila {line_number}: código duplicado {code}")
        seen_codes.add(code)

        cuit = values.get("cuit") or None
        if cuit:
            cuit = _validate_cuit(cuit)[0]

        name_upper = name.upper()
        record = {
            "codigo": code,
            "nombre": name,
            "cuit": cuit,
            "direccion": values.get("direccion") or None,
            "telefono": values.get("telefono") or None,
            "localidad": values.get("localidad") or None,
            "provincia": values.get("provincia") or None,
            "email": values.get("email") or None,
            "activo": 0 if "NO USAR" in name_upper else 1,
        }
        limits = {
            "codigo": 64,
            "nombre": 160,
            "cuit": 20,
            "direccion": 255,
            "telefono": 64,
            "localidad": 128,
            "provincia": 128,
            "email": 512,
        }
        for field, limit in limits.items():
            value = record[field]
            if isinstance(value, str) and len(value) > limit:
                raise ValueError(
                    f"Fila {line_number}: {field} excede el máximo de {limit} caracteres"
                )
        records.append(record)

    if not records:
        raise ValueError("El CSV no contiene proveedores válidos")
    return records


def reconcile(path: Path, *, apply: bool) -> dict[str, int]:
    records = load_source(path)
    settings = get_settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    source_codes = [record["codigo"] for record in records]
    source_set = set(source_codes)

    try:
        with engine.connect() as conn:
            email_length = conn.execute(
                text(
                    """SELECT CHARACTER_MAXIMUM_LENGTH
                       FROM information_schema.COLUMNS
                       WHERE TABLE_SCHEMA = DATABASE()
                         AND TABLE_NAME = 'proveedor' AND COLUMN_NAME = 'email'"""
                )
            ).scalar_one_or_none()
            if email_length is None or (apply and email_length < 512):
                raise RuntimeError(
                    "La migración 018 debe estar aplicada (proveedor.email VARCHAR(512))"
                )
            existing = conn.execute(
                text("SELECT id, codigo, activo FROM proveedor")
            ).mappings().all()
            existing_by_code = {str(row["codigo"]).strip(): row for row in existing}
            absent = [
                row for row in existing
                if str(row["codigo"]).strip() not in source_set
            ]
            expected_active = sum(record["activo"] for record in records)
            summary = {
                "source_rows": len(records),
                "matched": sum(code in existing_by_code for code in source_set),
                "inserted": sum(code not in existing_by_code for code in source_set),
                "deactivated_absent": sum(bool(row["activo"]) for row in absent),
                "deactivated_no_usar": sum(not record["activo"] for record in records),
                "historical_evaluation_rows_preserved": conn.execute(
                    text("SELECT COUNT(*) FROM evaluacion_proveedor_anual")
                ).scalar_one(),
                "expected_active_after": expected_active,
                "current_email_length": email_length,
                "applied": int(apply),
            }

        if not apply:
            return summary

        with engine.begin() as conn:
            current = conn.execute(
                text("SELECT id, codigo, activo FROM proveedor")
            ).mappings().all()
            absent_ids = [
                row["id"] for row in current
                if str(row["codigo"]).strip() not in source_set
            ]

            for start in range(0, len(records), 500):
                conn.execute(UPSERT, records[start : start + 500])

            for start in range(0, len(absent_ids), 500):
                conn.execute(
                    text("UPDATE proveedor SET activo = 0 WHERE id IN :ids").bindparams(
                        bindparam("ids", expanding=True)
                    ),
                    {"ids": absent_ids[start : start + 500]},
                )

            source_present = conn.execute(
                text("SELECT COUNT(*) FROM proveedor WHERE codigo IN :codes").bindparams(
                    bindparam("codes", expanding=True)
                ),
                {"codes": source_codes},
            ).scalar_one()
            active_after = conn.execute(
                text("SELECT COUNT(*) FROM proveedor WHERE activo = 1")
            ).scalar_one()
            if source_present != len(records) or active_after != expected_active:
                raise RuntimeError(
                    "Verificación fallida; se revierte la transacción "
                    f"(source_present={source_present}/{len(records)}, "
                    f"active={active_after}/{expected_active})"
                )
            summary["total_after"] = conn.execute(
                text("SELECT COUNT(*) FROM proveedor")
            ).scalar_one()
            summary["active_after"] = active_after

        return summary
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="aplica la conciliación; sin esta opción solo muestra el plan",
    )
    args = parser.parse_args()
    summary = reconcile(args.csv_path, apply=args.apply)
    print(summary)


if __name__ == "__main__":
    main()
