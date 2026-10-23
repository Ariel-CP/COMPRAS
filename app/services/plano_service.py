from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pypdf import PdfReader

from app.core.config import get_settings


@lru_cache(maxsize=8)
def _catalogar_planos_pdf_cached(
    directorio: str, _modified_ns: int
) -> dict[str, dict[str, Path]]:
    catalogo: dict[str, dict[str, Path]] = {}
    pattern = re.compile(r"(\d{4})(?:-([A-Z]))?\.pdf$", re.IGNORECASE)
    try:
        for file_path in Path(directorio).glob("*.pdf"):
            match = pattern.fullmatch(file_path.name)
            if match and file_path.is_file():
                numero_base = match.group(1)
                revision = (match.group(2) or "").upper()
                catalogo.setdefault(numero_base, {})[revision] = file_path
    except OSError:
        return {}
    return catalogo


def catalogar_planos_pdf(directorio: str | None = None) -> dict[str, dict[str, Path]]:
    """Indexa PDFs por número y revisión; refresca si cambia la carpeta."""
    base_dir = Path(directorio or get_settings().planos_dir)
    try:
        modified_ns = base_dir.stat().st_mtime_ns
    except OSError:
        return {}
    return _catalogar_planos_pdf_cached(str(base_dir), modified_ns)


def resolver_plano_catalogado(
    numero_plano: str, catalogo: dict[str, dict[str, Path]]
) -> Optional[Path]:
    """Resuelve una revisión explícita o la revisión más alta disponible."""
    match = re.fullmatch(r"(\d{4})(?:-([A-Z]))?", numero_plano, re.IGNORECASE)
    if not match:
        return None

    numero_base = match.group(1)
    revision_solicitada = (match.group(2) or "").upper()
    archivos = catalogo.get(numero_base, {})
    if revision_solicitada:
        return archivos.get(revision_solicitada)
    revisiones = [revision for revision in archivos if revision]
    if revisiones:
        return archivos[max(revisiones)]
    return archivos.get("")


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


@lru_cache(maxsize=256)
def _leer_metadatos_pdf_cached(
    ruta: str, modified_ns: int, file_size: int
) -> dict[str, str]:
    del modified_ns, file_size
    reader = PdfReader(ruta, strict=False)
    metadata = reader.metadata
    if metadata is None:
        return {}

    campos = {
        "/Title": "titulo",
        "/Author": "autor",
        "/Subject": "asunto",
        "/Keywords": "palabras_clave",
        "/Creator": "creador",
        "/Producer": "productor_pdf",
        "/CreationDate": "fecha_creacion",
        "/ModDate": "fecha_modificacion",
    }
    resultado = {}
    for clave_pdf, clave_salida in campos.items():
        valor = metadata.get(clave_pdf)
        if valor is None:
            continue
        texto = str(valor).replace("\x00", " ").strip()
        if texto:
            resultado[clave_salida] = texto[:500]
    return resultado


def obtener_metadatos_plano(
    numero_plano: str, directorio: str | None = None
) -> dict[str, str]:
    """Lee metadatos PDF del plano y cachea el resultado por versión del archivo."""
    ruta = obtener_plano_pdf(numero_plano, directorio)
    stat = ruta.stat()
    return _leer_metadatos_pdf_cached(str(ruta), stat.st_mtime_ns, stat.st_size)
