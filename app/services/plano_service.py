from __future__ import annotations

import re
from pathlib import Path

from app.core.config import get_settings


def obtener_plano_pdf(numero_plano: str, directorio: str | None = None) -> Path:
    """Busca la revisión solicitada o la más alta de un plano de cuatro dígitos."""
    match_solicitado = re.fullmatch(r"(\d{4})(?:-([A-Z]))?", numero_plano, re.IGNORECASE)
    if not match_solicitado:
        raise ValueError("El número de plano debe ser NNNN o NNNN-letra")

    base_dir = Path(directorio or get_settings().planos_dir)
    numero_base = match_solicitado.group(1)
    revision_solicitada = match_solicitado.group(2)
    revision_pattern = re.compile(
        rf"{re.escape(numero_base)}-([A-Z])\.pdf$",
        re.IGNORECASE,
    )
    revisiones = []
    for file_path in base_dir.glob(f"{numero_base}-*.pdf"):
        match = revision_pattern.fullmatch(file_path.name)
        if match and file_path.is_file():
            revisiones.append((match.group(1).upper(), file_path))

    if revision_solicitada:
        for revision, file_path in revisiones:
            if revision == revision_solicitada.upper():
                return file_path
        raise FileNotFoundError(
            f"No se encontró el plano {numero_base}-{revision_solicitada.upper()}.pdf"
        )

    if revisiones:
        return max(revisiones, key=lambda item: item[0])[1]

    file_path = base_dir / f"{numero_base}.pdf"
    if file_path.is_file():
        return file_path
    raise FileNotFoundError(f"No se encontró el plano {numero_base} ni sus revisiones")
