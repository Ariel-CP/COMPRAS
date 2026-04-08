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

from app.core.version import APP_VERSION

logger = logging.getLogger(__name__)

# Ruta al script de actualización (relativa a la raíz del repo)
_UPDATE_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "update.sh"


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
        # ls-remote no necesita fetch; solo una llamada HTTP a GitHub
        raw = _run(["git", "ls-remote", "origin", "HEAD"], timeout=8)
        remote_full = raw.split()[0] if raw else ""
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

    available = bool(remote_full) and not remote_full.startswith(
        _run(["git", "rev-parse", "HEAD"])
    )

    improvements: list[str] = []
    if available:
        try:
            # Obtiene los objetos remotos y usa FETCH_HEAD como referencia temporal.
            _run(["git", "fetch", "--quiet", "origin", "HEAD"], timeout=20)
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

    try:
        subprocess.Popen(
            ["bash", str(_UPDATE_SCRIPT)],
            start_new_session=True,          # desacopla del proceso padre
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ},
        )
    except OSError as exc:
        raise RuntimeError(f"No se pudo lanzar el script de actualización: {exc}") from exc

    logger.info("Script de actualización lanzado: %s", _UPDATE_SCRIPT)
    return {"status": "updating", "message": "Actualización iniciada. El servicio va a reiniciar."}
