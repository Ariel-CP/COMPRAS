r"""Reparar mojibake UTF-8/Latin-1 en campos de texto de la base.

Uso:
    .venv\Scripts\python.exe scripts\ops\repair_text_encoding.py

Por defecto ejecuta un dry-run: solo muestra qué filas cambiarían.
Para aplicar cambios reales, agregar --apply.

El script corrige textos del estilo ``GenÃ©rico`` -> ``Genérico`` en tablas
de maestros y precios. No intenta reparar corrupción con caracteres de
reemplazo ``�``.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Iterable

from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import _engine  # noqa: E402


TEXT_COLUMNS: dict[str, list[str]] = {
    "producto": ["codigo", "nombre", "rubro"],
    "proveedor": [
        "codigo",
        "nombre",
        "contacto_nombre",
        "email",
        "telefono",
        "cuit",
        "direccion",
        "localidad",
        "provincia",
        "notas",
    ],
    "rubro": ["nombre"],
    "unidad_medida": ["codigo", "nombre"],
    "precio_compra_hist": [
        "proveedor_codigo",
        "proveedor_nombre",
        "referencia_doc",
        "notas",
    ],
    "precio_compra_import_lote": ["archivo_nombre", "mensaje_error"],
}


def _fix_mojibake_text(value: object) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    if not text_value:
        return ""
    if not any(marker in text_value for marker in ("Ã", "Â", "â")):
        return text_value
    try:
        repaired = text_value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text_value
    repaired = repaired.strip()
    return repaired or text_value


def _iter_tables(selected: str) -> Iterable[tuple[str, list[str]]]:
    if selected == "all":
        yield from TEXT_COLUMNS.items()
        return
    requested = {item.strip() for item in selected.split(",") if item.strip()}
    for table_name, columns in TEXT_COLUMNS.items():
        if table_name in requested:
            yield table_name, columns


def _repair_table(conn, table_name: str, columns: list[str], apply_changes: bool) -> int:
    select_columns = ", ".join(["id", *columns])
    rows = conn.execute(text(f"SELECT {select_columns} FROM {table_name}")).mappings().all()
    total_changes = 0

    for row in rows:
        changes: dict[str, object] = {}
        before: dict[str, object] = {}
        for column in columns:
            original = row[column]
            repaired = _fix_mojibake_text(original)
            if repaired != original:
                changes[column] = repaired
                before[column] = original

        if not changes:
            continue

        total_changes += 1
        print(f"[{table_name}] id={row['id']} -> {before} => {changes}")
        if apply_changes:
            set_clause = ", ".join([f"{column} = :{column}" for column in changes])
            params = {"id": row["id"], **changes}
            conn.execute(text(f"UPDATE {table_name} SET {set_clause} WHERE id = :id"), params)

    return total_changes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repara mojibake en textos de la base")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica los cambios en la base de datos en lugar de solo mostrarlos",
    )
    parser.add_argument(
        "--tables",
        default="all",
        help="Lista separada por comas de tablas a reparar o 'all' (default)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    selected_tables = list(_iter_tables(args.tables))
    if not selected_tables:
        print("No se seleccionó ninguna tabla para reparar")
        return 1

    mode = "APLICAR" if args.apply else "DRY-RUN"
    print(f"Modo: {mode}")
    print(f"Tablas: {', '.join(name for name, _ in selected_tables)}")

    total_rows = 0
    with _engine.connect() as conn:
        transaction = conn.begin()
        try:
            for table_name, columns in selected_tables:
                changed = _repair_table(conn, table_name, columns, args.apply)
                total_rows += changed

            if args.apply:
                transaction.commit()
            else:
                transaction.rollback()
        except Exception:
            transaction.rollback()
            raise

    print(f"Filas con cambios detectados: {total_rows}")
    if args.apply:
        print("Cambios aplicados correctamente")
    else:
        print("Dry-run completado; ejecuta con --apply para modificar la base")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())