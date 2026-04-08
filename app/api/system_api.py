"""Endpoints de estado y actualización del sistema."""
import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps_auth import require_permission
from app.services.system_service import get_update_status, trigger_update

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/update-status")
def update_status(
    _current_user: dict = Depends(require_permission("admin_sistema", False)),
):
    """Retorna si hay una actualización disponible comparando commit local vs remoto."""
    try:
        return get_update_status()
    except (RuntimeError, OSError, ValueError) as exc:
        logger.warning("Error al consultar estado de actualización: %s", exc)
        return {
            "available": False,
            "local_commit": "N/A",
            "remote_commit": "N/A",
            "git_available": False,
            "script_available": False,
            "improvements": [],
            "improvements_total": 0,
        }


@router.post("/update")
def run_update(
    _current_user: dict = Depends(require_permission("admin_sistema", True)),
):
    """Lanza el script update.sh y retorna inmediatamente.

    El servicio va a reiniciar; el cliente debe hacer polling a /api/health/db.
    """
    try:
        return trigger_update()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
