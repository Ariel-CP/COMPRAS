"""Servicio de estado y actualización del sistema.

Provee dos operaciones:
- get_update_status(): compara commit local vs remoto en GitHub.
- trigger_update(): lanza update.sh de forma desacoplada (el proceso reinicia
  el servicio, por eso el script se ejecuta en sesión separada y la función
  retorna antes de que termine).
"""
import logging
import os
import subprocess
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.version import APP_VERSION

logger = logging.getLogger(__name__)

# Ruta al script de actualización (relativa a la raíz del repo)
_UPDATE_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "update.sh"
_UPDATE_LOG = Path(__file__).resolve().parents[2] / "logs" / "update.log"
_LOGO_DIR = Path(__file__).resolve().parents[1] / "static" / "uploads"
_LOGO_PARAM_KEY = "ui_logo_path"
_MAX_LOGO_BYTES = 2 * 1024 * 1024
_ALLOWED_LOGO_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".svg"}


def _normalize_improvement_line(line: str) -> str:
    cleaned = " ".join((line or "").strip().split())
    if not cleaned:
        return ""
    return cleaned[0].upper() + cleaned[1:] if len(cleaned) > 1 else cleaned.upper()


def _humanize_improvement_line(line: str) -> str:
    normalized = _normalize_improvement_line(line)
    lower = normalized.casefold()

    replacements: tuple[tuple[str, str], ...] = (
        ("fix ", "Se corrigió "),
        ("fix:", "Se corrigió: "),
        ("fixed ", "Se corrigió "),
        ("add ", "Se agregó "),
        ("add:", "Se agregó: "),
        ("added ", "Se agregó "),
        ("feat ", "Se incorporó "),
        ("feat:", "Se incorporó: "),
        ("feature ", "Se incorporó "),
        ("feature:", "Se incorporó: "),
        ("improve ", "Se mejoró "),
        ("improve:", "Se mejoró: "),
        ("improved ", "Se mejoró "),
        ("update ", "Se actualizó "),
        ("update:", "Se actualizó: "),
        ("updated ", "Se actualizó "),
        ("refactor ", "Se refactorizó "),
        ("refactor:", "Se refactorizó: "),
        ("docs ", "Se documentó "),
        ("docs:", "Se documentó: "),
    )
    for prefix, replacement in replacements:
        if lower.startswith(prefix):
            return replacement + normalized[len(prefix):].strip()

    return normalized


def _run(cmd: list[str], timeout: int = 10) -> str:
    """Ejecuta un comando y retorna stdout; lanza RuntimeError si falla."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Comando falló: {cmd}")
    return result.stdout.strip()


def get_update_status() -> dict:
    """Compara el commit local HEAD con el remoto origin/master.

    Returns:
        {
            "available": bool,      # True si hay actualización disponible
            "local_commit":  str,   # SHA corto local
            "remote_commit": str,   # SHA corto remoto
            "git_available": bool,  # False si git no está instalado
            "script_available": bool,  # False si update.sh no existe
        }
    """
    script_available = _UPDATE_SCRIPT.exists()

    try:
        local = _run(["git", "rev-parse", "--short", "HEAD"])
    except (RuntimeError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("No se pudo obtener commit local: %s", exc)
        return {
            "available": False,
            "local_commit": "N/A",
            "remote_commit": "N/A",
            "git_available": False,
            "script_available": script_available,
            "improvements": [],
            "improvements_total": 0,
        }

    try:
        # Fetch para obtener FETCH_HEAD actualizado con los últimos commits remotos.
        _run(["git", "fetch", "--quiet", "origin", "HEAD"], timeout=20)
        remote_full = _run(["git", "rev-parse", "FETCH_HEAD"])
        remote = remote_full[:7] if remote_full else "N/A"
    except (RuntimeError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("No se pudo consultar remote: %s", exc)
        remote = "N/A"
        return {
            "available": False,
            "local_commit": local,
            "remote_commit": remote,
            "git_available": True,
            "script_available": script_available,
            "improvements": [],
            "improvements_total": 0,
        }

    # Cuenta cuántos commits del remoto NO están en local (local está "detrás").
    # Si local tiene commits sin push (está adelante), behind_count = 0 → no hay update.
    try:
        behind_count = int(_run(["git", "rev-list", "HEAD..FETCH_HEAD", "--count"]))
        available = behind_count > 0
    except (RuntimeError, ValueError, subprocess.TimeoutExpired):
        available = False

    improvements: list[str] = []
    if available:
        try:
            raw_commits = _run(
                [
                    "git",
                    "log",
                    "--no-merges",
                    "--pretty=format:%s",
                    "HEAD..FETCH_HEAD",
                    "-n",
                    "8",
                ],
                timeout=10,
            )
            if raw_commits:
                seen: set[str] = set()
                improvements = []
                for line in raw_commits.splitlines():
                    cleaned = _normalize_improvement_line(line)
                    if not cleaned:
                        continue
                    normalized_key = cleaned.casefold()
                    if normalized_key in seen:
                        continue
                    seen.add(normalized_key)
                    improvements.append(_humanize_improvement_line(cleaned))
        except (RuntimeError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
            logger.warning("No se pudo construir resumen de mejoras: %s", exc)

    return {
        "available": available,
        "local_commit": local,
        "remote_commit": remote,
        "current_version": APP_VERSION,
        "git_available": True,
        "script_available": script_available,
        "improvements": improvements,
        "improvements_total": len(improvements),
    }


def trigger_update() -> dict:
    """Lanza update.sh en segundo plano en una sesión separada.

    El script reiniciará el servicio systemd, por lo que esta función
    retorna ANTES de que eso ocurra. El cliente debe hacer polling
    a /api/health/db hasta que vuelva a responder.

    Raises:
        FileNotFoundError: si update.sh no existe.
        RuntimeError: si no se puede lanzar el subproceso.
    """
    if not _UPDATE_SCRIPT.exists():
        raise FileNotFoundError(f"Script no encontrado: {_UPDATE_SCRIPT}")

    _UPDATE_LOG.parent.mkdir(parents=True, exist_ok=True)

    try:
        with _UPDATE_LOG.open("a", encoding="utf-8") as log_file:
            log_file.write("\n===== update start =====\n")
        subprocess.Popen(
            ["bash", str(_UPDATE_SCRIPT)],
            start_new_session=True,          # desacopla del proceso padre
            stdout=_UPDATE_LOG.open("a", encoding="utf-8"),
            stderr=subprocess.STDOUT,
            env={**os.environ},
        )
    except OSError as exc:
        raise RuntimeError(f"No se pudo lanzar el script de actualización: {exc}") from exc

    logger.info("Script de actualización lanzado: %s", _UPDATE_SCRIPT)
    return {
        "status": "updating",
        "message": "Actualización iniciada. El servicio va a reiniciar.",
        "log_path": str(_UPDATE_LOG),
    }


def get_ui_logo(db: Session) -> dict:
    row = db.execute(
        text("SELECT valor FROM parametro_sistema WHERE clave = :key LIMIT 1"),
        {"key": _LOGO_PARAM_KEY},
    ).fetchone()
    logo_url = row[0] if row and row[0] else None
    if logo_url:
        normalized = str(logo_url).strip()
        if normalized.startswith("/static/uploads/"):
            rel_path = normalized.removeprefix("/static/")
            file_path = Path(__file__).resolve().parents[1] / rel_path
            logo_url = normalized if file_path.exists() else None
        else:
            logo_url = None
    return {"logo_url": logo_url}


def save_ui_logo(
    db: Session,
    *,
    file_bytes: bytes,
    original_filename: str,
    content_type: str | None,
) -> dict:
    if not file_bytes:
        raise ValueError("El archivo está vacío")
    if len(file_bytes) > _MAX_LOGO_BYTES:
        raise ValueError("El logo supera el tamaño máximo permitido (2 MB)")

    suffix = Path(original_filename or "").suffix.lower()
    if suffix not in _ALLOWED_LOGO_SUFFIXES:
        raise ValueError("Formato no permitido. Use PNG, JPG, JPEG, WEBP o SVG")

    normalized_content_type = (content_type or "").lower()
    if normalized_content_type and not normalized_content_type.startswith("image/"):
        raise ValueError("El archivo seleccionado no es una imagen válida")

    _LOGO_DIR.mkdir(parents=True, exist_ok=True)
    for existing in _LOGO_DIR.glob("logo_custom.*"):
        existing.unlink(missing_ok=True)

    final_name = f"logo_custom{suffix}"
    final_path = _LOGO_DIR / final_name
    final_path.write_bytes(file_bytes)

    logo_url = f"/static/uploads/{final_name}"
    db.execute(
        text(
            """
            INSERT INTO parametro_sistema (clave, valor, descripcion)
            VALUES (:key, :value, :description)
            ON DUPLICATE KEY UPDATE valor = VALUES(valor), descripcion = VALUES(descripcion)
            """
        ),
        {
            "key": _LOGO_PARAM_KEY,
            "value": logo_url,
            "description": "Logo visible en cabecera de la aplicación",
        },
    )
    db.commit()
    return {"logo_url": logo_url}
