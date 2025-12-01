"""Utility to sanitize Flexxus MBOM exports before importing into COMPRAS.

The script reads the raw CSV, moves process metadata into CodArt/Descripcion and
writes a cleaned copy without the original "Articulo" column.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable, List, Tuple

PROCESS_PATTERN = re.compile(r"proceso\s+(?P<num>\d+)\s*-\s*(?P<label>[^-]+)", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Limpia archivos MBOM exportados desde Flexxus")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("CECO1EI012.csv"),
        help="Ruta del CSV original exportado desde Flexxus",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("import/CECO1EI012_limpio.csv"),
        help="Ruta destino del CSV depurado",
    )
    parser.add_argument(
        "--encoding",
        default="latin-1",
        help="Encoding a utilizar al leer/escribir (default: latin-1)",
    )
    return parser.parse_args()


def find_articulo_column(headers: Iterable[str]) -> str:
    for header in headers:
        normalized = header.lower().replace("�", "\u00ed")
        if normalized.startswith("art") and "culo" in normalized:
            return header
    raise ValueError("No se encontro la columna 'Articulo' en el archivo")


def normalize_row(row: dict, articulo_col: str) -> Tuple[dict, bool]:
    cod_art = row.get("CodArt", "").strip()
    articulo_val = row.get(articulo_col, "").strip()
    if cod_art or not articulo_val:
        return row, False

    match = PROCESS_PATTERN.search(articulo_val)
    if not match:
        return row, False

    numero = match.group("num").strip()
    etiqueta = match.group("label").strip(" -")
    row["CodArt"] = f"PROCESO {numero}"
    row["Descripcion"] = etiqueta or row.get("Descripcion", "").strip()
    return row, True


def load_rows(path: Path, encoding: str) -> Tuple[List[dict], str]:
    with path.open("r", encoding=encoding, newline="") as handler:
        reader = csv.DictReader(handler, delimiter=";")
        articulo_col = find_articulo_column(reader.fieldnames or [])
        rows = list(reader)
    return rows, articulo_col


def write_rows(path: Path, rows: Iterable[dict], headers: List[str], encoding: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=encoding, newline="") as handler:
        writer = csv.DictWriter(handler, fieldnames=headers, delimiter=";")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in headers})


def main() -> None:
    args = parse_args()
    rows, articulo_col = load_rows(args.input, args.encoding)
    if not rows:
        raise ValueError("El CSV no contiene filas para procesar")

    updated_count = 0
    for row in rows:
        _, updated = normalize_row(row, articulo_col)
        if updated:
            updated_count += 1

    output_headers = [col for col in rows[0].keys() if col != articulo_col]
    write_rows(args.output, rows, output_headers, args.encoding)

    print(
        "Archivo limpiado guardado en "
        f"{args.output}. Filas de proceso actualizadas: {updated_count}"
    )


if __name__ == "__main__":
    main()
