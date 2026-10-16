"""Importa un snapshot crudo de Access al staging versionado."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    repository_root = str(Path(__file__).resolve().parents[2])
    if repository_root not in sys.path:
        sys.path.insert(0, repository_root)

    from app.core.config import get_settings
    from app.db import get_db
    from app.services.recepcion_access_snapshot_service import (
        SOURCE_TABLES,
        importar_snapshot_access,
    )

    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--access-path",
        default=settings.access_db_path,
        help="Ruta de Access; por defecto usa ACCESS_DB_PATH/configuración.",
    )
    parser.add_argument(
        "--usuario-id",
        type=int,
        required=True,
        help="ID del usuario responsable de la corrida de importación.",
    )
    parser.add_argument(
        "--tabla",
        choices=tuple(SOURCE_TABLES),
        action="append",
        dest="tablas",
        help="Tabla allowlisted a importar. Repetible; por defecto todas las habilitadas.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Filas por lote (1-5000).",
    )
    args = parser.parse_args(argv)
    if not args.access_path:
        parser.error("configurá ACCESS_DB_PATH o indicá --access-path")

    db_generator = get_db()
    db = next(db_generator)
    try:
        result = importar_snapshot_access(
            db,
            path=args.access_path,
            usuario_id=args.usuario_id,
            tablas=tuple(args.tablas) if args.tablas else tuple(SOURCE_TABLES),
            batch_size=args.batch_size,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()
        db_generator.close()


if __name__ == "__main__":
    raise SystemExit(main())
