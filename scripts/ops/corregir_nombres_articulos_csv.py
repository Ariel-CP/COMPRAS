"""Compara nombres de producto con un CSV; solo actualiza con --apply."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import SessionLocal  # noqa: E402


def reparar_codigo(valor: str) -> str:
    """Revierte UTF-8 leido como CP1252 solo para buscar coincidencias."""
    try:
        data = bytearray()
        for char in valor:
            if 0x80 <= ord(char) <= 0x9F:
                data.append(ord(char))
            else:
                data.extend(char.encode("cp1252"))
        return data.decode("utf-8")
    except (UnicodeError, ValueError):
        return valor


def leer_fuente(path: Path) -> tuple[dict[str, str], str, str]:
    raw = path.read_bytes()
    try:
        contenido = raw.decode("utf-8-sig")
        encoding = "utf-8-sig"
    except UnicodeDecodeError:
        contenido = raw.decode("cp1252")
        encoding = "cp1252"
    reader = csv.DictReader(io.StringIO(contenido), delimiter=";")
    if reader.fieldnames != ["C\u00f3digo", "Descripci\u00f3n"]:
        raise ValueError("El CSV debe tener las columnas Codigo y Descripcion")
    fuente: dict[str, str] = {}
    for numero, row in enumerate(reader, 2):
        codigo = (row.get("C\u00f3digo") or "").strip()
        nombre = (row.get("Descripci\u00f3n") or "").strip()
        if None in row or not codigo or not nombre or len(nombre) > 128:
            raise ValueError(f"Fila {numero} invalida o nombre mayor a 128 caracteres")
        if codigo in fuente and fuente[codigo] != nombre:
            raise ValueError(f"Codigo duplicado con nombres distintos: {codigo}")
        fuente[codigo] = nombre
    if not fuente:
        raise ValueError("El CSV no contiene articulos")
    return fuente, encoding, hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT_DIR / "TEMP" / "correccion_nombres"
    )
    args = parser.parse_args()
    fuente, encoding, digest = leer_fuente(args.csv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).strftime(
        "%Y%m%d_%H%M%S_%f"
    )
    reporte = {
        "fuente": str(args.csv.resolve()),
        "sha256": digest,
        "encoding": encoding,
        "aplicado": False,
        "cambios": [],
        "sin_coincidencia": [],
        "ambiguos": [],
        "iguales": 0,
    }
    with SessionLocal() as db:
        with db.begin():
            query = "SELECT id, codigo, nombre FROM producto ORDER BY id"
            if args.apply:
                query += " FOR UPDATE"
            productos = [dict(row) for row in db.execute(text(query)).mappings()]
            por_codigo = {row["codigo"]: row for row in productos}
            normalizados = defaultdict(list)
            for row in productos:
                normalizados[reparar_codigo(row["codigo"])].append(row)
            usados = set()
            for codigo, nombre in fuente.items():
                candidatos = (
                    [por_codigo[codigo]]
                    if codigo in por_codigo
                    else normalizados.get(codigo, [])
                )
                if not candidatos:
                    reporte["sin_coincidencia"].append(
                        {"codigo": codigo, "nombre": nombre}
                    )
                    continue
                if len(candidatos) != 1 or candidatos[0]["id"] in usados:
                    reporte["ambiguos"].append(
                        {"codigo": codigo, "ids": [r["id"] for r in candidatos]}
                    )
                    continue
                producto = candidatos[0]
                usados.add(producto["id"])
                if producto["nombre"] == nombre:
                    reporte["iguales"] += 1
                    continue
                reporte["cambios"].append(
                    {
                        "id": producto["id"],
                        "codigo_bd": producto["codigo"],
                        "codigo_csv": codigo,
                        "anterior": producto["nombre"],
                        "nuevo": nombre,
                    }
                )
            if reporte["ambiguos"]:
                raise ValueError(
                    "Existen coincidencias ambiguas; no se actualizo ningun producto"
                )
            backup = args.output_dir / f"comparacion_{stamp}.json"
            backup.write_text(
                json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            if args.apply:
                for cambio in reporte["cambios"]:
                    result = db.execute(
                        text("UPDATE producto SET nombre = :nuevo WHERE id = :id"),
                        cambio,
                    )
                    if result.rowcount != 1:
                        raise RuntimeError("No se actualizo exactamente un producto")
                actuales = {
                    r.id: r.nombre
                    for r in db.execute(text("SELECT id,nombre FROM producto"))
                }
                if any(actuales[c["id"]] != c["nuevo"] for c in reporte["cambios"]):
                    raise RuntimeError(
                        "Fallo la validacion; se revierte la transaccion"
                    )
    if args.apply:
        with SessionLocal() as db:
            actuales = {
                r.id: r.nombre
                for r in db.execute(text("SELECT id,nombre FROM producto"))
            }
        if any(actuales[c["id"]] != c["nuevo"] for c in reporte["cambios"]):
            raise RuntimeError("La verificacion posterior al commit fallo")
        reporte["aplicado"] = True
        backup.write_text(
            json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "aplicado": reporte["aplicado"],
                "fuente": len(fuente),
                "cambios": len(reporte["cambios"]),
                "iguales": reporte["iguales"],
                "sin_coincidencia": len(reporte["sin_coincidencia"]),
                "ambiguos": len(reporte["ambiguos"]),
                "reporte": str(backup),
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
