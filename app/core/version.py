"""Fuente de verdad de la versión del sistema.

Lee el archivo VERSION en la raíz del repo. Si no existe, retorna 'dev'.
"""
from pathlib import Path

_VERSION_FILE = Path(__file__).resolve().parents[2] / "VERSION"


def get_version() -> str:
    try:
        return _VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "dev"


APP_VERSION: str = get_version()
