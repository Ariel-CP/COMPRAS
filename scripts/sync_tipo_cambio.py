"""Sincroniza tipos de cambio oficiales del BCRA."""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.services.tipo_cambio_sync_service import (  # noqa: E402
    TipoCambioSyncError,
    sync_bcra_tipos_cambio,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sincroniza tasas USD y USD_MAY desde el BCRA"
    )
    parser.add_argument(
        "--desde",
        type=date.fromisoformat,
        help="Fecha inicial (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--hasta",
        type=date.fromisoformat,
        help="Fecha final (YYYY-MM-DD)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    db = SessionLocal()
    try:
        resumen = sync_bcra_tipos_cambio(
            db,
            desde=args.desde,
            hasta=args.hasta,
        )
        db.commit()
        print(
            "Sincronización completada: "
            f"{resumen.insertados} insertados, "
            f"{resumen.actualizados} actualizados, "
            f"{resumen.procesados} procesados "
            f"(rango {resumen.desde} -> {resumen.hasta})"
        )
    except TipoCambioSyncError as exc:
        db.rollback()
        print(f"Error: {exc}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
