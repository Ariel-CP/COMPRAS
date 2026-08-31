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
from fastapi import Body
from pathlib import Path
import json

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_APP_CONFIG_PATH = _PROJECT_ROOT / "app" / "config.json"

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


@router.get("/settings")
def get_settings_ui(
    _current_user: dict = Depends(require_permission("admin_sistema", False)),
):
    """Retorna el contenido de `app/config.json` (solo claves públicas)."""
    try:
        if not _APP_CONFIG_PATH.exists():
            return {}
        with _APP_CONFIG_PATH.open("r", encoding="utf-8") as f:
            cfg = json.load(f)
        # No filtrar: la plantilla decide qué mostrar. Retornamos el objeto.
        return cfg
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/settings")
def save_settings_ui(
    payload: dict = Body(...),
    _current_user: dict = Depends(require_permission("admin_sistema", True)),
):
    """Guarda parámetros en `app/config.json`. Se hace merge con valores existentes."""
    try:
        cfg = {}
        if _APP_CONFIG_PATH.exists():
            with _APP_CONFIG_PATH.open("r", encoding="utf-8") as f:
                try:
                    cfg = json.load(f) or {}
                except json.JSONDecodeError:
                    cfg = {}
        # Solo permitir claves conocidas/parciales para evitar sobrescribir todo.
        allowed = {"bcra_api_token", "bcra_api_base_url", "bcra_sync_days"}
        for k, v in payload.items():
            if k in allowed:
                cfg[k] = v
        # Escribir de vuelta
        with _APP_CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return {"status": "ok"}
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
