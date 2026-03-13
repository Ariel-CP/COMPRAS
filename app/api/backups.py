from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps_auth import require_permission
from app.db import get_db
from app.services import backup_service

router = APIRouter()


class BackupPreferencesIn(BaseModel):
    auto_enabled: bool = False
    auto_time: str = "02:00"
    auto_dir: str | None = None
    auto_weekdays: list[int] = []
    favorite_dirs: list[str] = []


@router.get("/")
def listar_backups(
    backup_dir: str | None = Query(default=None),
    _current_user: dict = Depends(require_permission("admin_backups", False))
):
    try:
        return backup_service.list_backups(backup_dir=backup_dir)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/preferences")
def obtener_preferencias_backup(
    db: Session = Depends(get_db),
    _current_user: dict = Depends(require_permission("admin_backups", False)),
):
    return backup_service.get_backup_preferences(db)


@router.put("/preferences")
def guardar_preferencias_backup(
    payload: BackupPreferencesIn,
    db: Session = Depends(get_db),
    _current_user: dict = Depends(require_permission("admin_backups", True)),
):
    try:
        return backup_service.update_backup_preferences(
            db,
            auto_enabled=payload.auto_enabled,
            auto_time=payload.auto_time,
            auto_dir=payload.auto_dir,
            auto_weekdays=payload.auto_weekdays,
            favorite_dirs=payload.favorite_dirs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/", status_code=status.HTTP_201_CREATED)
def crear_backup(
    backup_dir: str | None = Query(default=None),
    _current_user: dict = Depends(require_permission("admin_backups", True))
):
    try:
        return backup_service.create_backup(backup_dir=backup_dir)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{filename}/download")
def descargar_backup(
    filename: str,
    backup_dir: str | None = Query(default=None),
    _current_user: dict = Depends(require_permission("admin_backups", False)),
):
    try:
        path = backup_service.get_backup_path(filename, backup_dir=backup_dir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, filename=path.name, media_type="application/sql")


@router.delete("/{filename}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_backup(
    filename: str,
    backup_dir: str | None = Query(default=None),
    _current_user: dict = Depends(require_permission("admin_backups", True)),
):
    try:
        backup_service.delete_backup(filename, backup_dir=backup_dir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return None


@router.post("/restore")
async def restaurar_backup(
    file: UploadFile = File(...),
    confirm_overwrite: bool = Form(False),
    confirm_data_loss: bool = Form(False),
    confirm_text: str = Form(""),
    create_safety_backup: bool = Form(True),
    backup_dir: str | None = Form(default=None),
    _current_user: dict = Depends(require_permission("admin_backups", True)),
):
    try:
        sql_bytes = await file.read()
        return backup_service.restore_uploaded_sql(
            sql_bytes=sql_bytes,
            original_filename=file.filename or "backup.sql",
            confirm_overwrite=confirm_overwrite,
            confirm_data_loss=confirm_data_loss,
            confirm_text=confirm_text,
            create_safety_backup=create_safety_backup,
            safety_backup_dir=backup_dir,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
