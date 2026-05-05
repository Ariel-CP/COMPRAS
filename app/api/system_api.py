"""Endpoints de estado y actualización del sistema."""
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps_auth import get_current_user, require_permission
from app.db import get_db
from app.services.system_service import (
    get_ui_logo,
    get_update_status,
    save_ui_logo,
    trigger_update,
)

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


@router.get("/logo")
def get_logo(
    db: Session = Depends(get_db),
    _current_user: dict = Depends(get_current_user),
):
    """Retorna URL del logo configurado para la cabecera."""
    return get_ui_logo(db)


@router.post("/logo")
async def upload_logo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _current_user: dict = Depends(require_permission("admin_sistema", True)),
):
    """Guarda el logo de cabecera y actualiza el parámetro de sistema."""
    try:
        file_bytes = await file.read()
        return save_ui_logo(
            db,
            file_bytes=file_bytes,
            original_filename=file.filename or "logo.png",
            content_type=file.content_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
