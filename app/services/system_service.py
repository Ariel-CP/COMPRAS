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


def _run(cmd: list[str], timeout: int = 10) -> str:
    """Ejecuta un comando y retorna stdout; lanza RuntimeError si falla."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
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
        }

    available = bool(remote_full) and not remote_full.startswith(
        _run(["git", "rev-parse", "HEAD"])
    )

    return {
        "available": available,
        "local_commit": local,
        "remote_commit": remote,
        "current_version": APP_VERSION,
        "git_available": True,
        "script_available": script_available,
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
