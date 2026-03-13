from __future__ import annotations

import os
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings


@dataclass(frozen=True)
class BackupTarget:
    host: str
    port: int
    username: str
    password: str | None
    database: str


PARAM_BACKUP_AUTO_ENABLED = "backup_auto_enabled"
PARAM_BACKUP_AUTO_TIME = "backup_auto_time"
PARAM_BACKUP_AUTO_DIR = "backup_auto_dir"
PARAM_BACKUP_AUTO_WEEKDAYS = "backup_auto_weekdays"
PARAM_BACKUP_FAVORITE_DIRS = "backup_favorite_dirs"
PARAM_BACKUP_AUTO_LAST_RUN = "backup_auto_last_run"
PARAM_BACKUP_AUTO_LAST_STATUS = "backup_auto_last_status"
PARAM_BACKUP_AUTO_LAST_MESSAGE = "backup_auto_last_message"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_backup_dir(backup_dir: str | None = None) -> Path:
    settings = get_settings()
    configured_raw = (backup_dir or "").strip() or settings.backup_dir
    configured = Path(configured_raw)
    if not configured.is_absolute():
        configured = _project_root() / configured
    configured.mkdir(parents=True, exist_ok=True)
    if not configured.is_dir():
        raise RuntimeError("El directorio de backup indicado no es valido")
    return configured


def _mysqldump_candidate() -> str:
    settings = get_settings()
    configured = (settings.mysqldump_path or "").strip()
    if configured:
        return configured
    return "mysqldump"


def _resolve_mysqldump() -> str | None:
    candidate = _mysqldump_candidate()
    if os.path.isabs(candidate) and Path(candidate).exists():
        return candidate
    resolved = shutil.which(candidate)
    return resolved or None


def _mysql_candidate() -> str:
    settings = get_settings()
    configured = (settings.mysql_client_path or "").strip()
    if configured:
        return configured
    return "mysql"


def _resolve_mysql_client() -> str | None:
    candidate = _mysql_candidate()
    if os.path.isabs(candidate) and Path(candidate).exists():
        return candidate
    resolved = shutil.which(candidate)
    return resolved or None


def _parse_database_target() -> BackupTarget:
    settings = get_settings()
    url = make_url(settings.database_url)
    if not url.host or not url.database or not url.username:
        raise RuntimeError("DATABASE_URL incompleta para generar backups")
    return BackupTarget(
        host=url.host,
        port=int(url.port or 3306),
        username=url.username,
        password=url.password,
        database=url.database,
    )


def _backup_filename(database: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{database}_{timestamp}.sql"


def _serialize_backup(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "filename": path.name,
        "size_bytes": stat.st_size,
        "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(
            timespec="seconds"
        ),
    }


def list_backups(backup_dir: str | None = None) -> dict[str, Any]:
    backup_dir_path = _resolve_backup_dir(backup_dir)
    items = [
        _serialize_backup(path)
        for path in sorted(
            backup_dir_path.glob("*.sql"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    ]
    tool_path = _resolve_mysqldump()
    mysql_path = _resolve_mysql_client()
    return {
        "items": items,
        "backup_dir": str(backup_dir_path),
        "mysqldump_available": bool(tool_path),
        "mysqldump_path": tool_path,
        "mysql_available": bool(mysql_path),
        "mysql_path": mysql_path,
    }


def create_backup(backup_dir: str | None = None) -> dict[str, Any]:
    target = _parse_database_target()
    mysqldump_path = _resolve_mysqldump()
    if not mysqldump_path:
        raise RuntimeError(
            "No se encontro mysqldump. Configure MYSQLDUMP_PATH o agreguelo al PATH."
        )

    backup_dir_path = _resolve_backup_dir(backup_dir)
    output_path = backup_dir_path / _backup_filename(target.database)
    command = [
        mysqldump_path,
        f"--host={target.host}",
        f"--port={target.port}",
        f"--user={target.username}",
        "--single-transaction",
        "--routines",
        "--triggers",
        "--default-character-set=utf8mb4",
        f"--result-file={output_path}",
        target.database,
    ]
    env = os.environ.copy()
    if target.password:
        env["MYSQL_PWD"] = target.password

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        stderr = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(stderr or "mysqldump finalizo con error")

    payload = _serialize_backup(output_path)
    payload["database"] = target.database
    payload["backup_dir"] = str(backup_dir_path)
    return payload


def get_backup_path(filename: str, backup_dir: str | None = None) -> Path:
    if not filename or Path(filename).name != filename:
        raise ValueError("Nombre de backup invalido")
    path = _resolve_backup_dir(backup_dir) / filename
    if not path.exists() or not path.is_file():
        raise FileNotFoundError("Backup no encontrado")
    return path


def delete_backup(filename: str, backup_dir: str | None = None) -> None:
    path = get_backup_path(filename, backup_dir=backup_dir)
    path.unlink(missing_ok=False)


def restore_uploaded_sql(
    sql_bytes: bytes,
    original_filename: str,
    confirm_overwrite: bool,
    confirm_data_loss: bool,
    confirm_text: str,
    create_safety_backup: bool = True,
    safety_backup_dir: str | None = None,
) -> dict[str, Any]:
    if not confirm_overwrite:
        raise RuntimeError("Debe confirmar sobreescritura")
    if not confirm_data_loss:
        raise RuntimeError("Debe confirmar posible perdida de datos")
    if (confirm_text or "").strip().upper() != "RESTAURAR":
        raise RuntimeError("Confirmacion invalida. Escriba RESTAURAR")
    if not original_filename or not original_filename.lower().endswith(".sql"):
        raise RuntimeError("Solo se permiten archivos .sql")
    if not sql_bytes:
        raise RuntimeError("El archivo SQL esta vacio")

    settings = get_settings()
    max_bytes = int(settings.max_upload_mb) * 1024 * 1024
    if len(sql_bytes) > max_bytes:
        raise RuntimeError(
            f"Archivo demasiado grande. Maximo {settings.max_upload_mb} MB"
        )

    mysql_path = _resolve_mysql_client()
    if not mysql_path:
        raise RuntimeError(
            "No se encontro mysql client. Configure MYSQL_CLIENT_PATH o agreguelo al PATH."
        )

    target = _parse_database_target()
    safety_backup_name: str | None = None
    if create_safety_backup:
        safety = create_backup(backup_dir=safety_backup_dir)
        safety_backup_name = str(safety.get("filename") or "") or None

    command = [
        mysql_path,
        f"--host={target.host}",
        f"--port={target.port}",
        f"--user={target.username}",
        "--default-character-set=utf8mb4",
        target.database,
    ]
    env = os.environ.copy()
    if target.password:
        env["MYSQL_PWD"] = target.password

    result = subprocess.run(
        command,
        input=sql_bytes,
        capture_output=True,
        text=False,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or b"").decode("utf-8", errors="ignore").strip()
        stdout = (result.stdout or b"").decode("utf-8", errors="ignore").strip()
        detail = stderr or stdout or "mysql finalizo con error"
        raise RuntimeError(detail)

    return {
        "ok": True,
        "message": "Restore completado",
        "database": target.database,
        "restored_filename": original_filename,
        "safety_backup_filename": safety_backup_name,
    }


def _is_valid_hhmm(value: str) -> bool:
    if not value:
        return False
    if not re.match(r"^\d{2}:\d{2}$", value):
        return False
    hour, minute = value.split(":", 1)
    return 0 <= int(hour) <= 23 and 0 <= int(minute) <= 59


def _get_param(db: Session, key: str, default: str = "") -> str:
    value = db.execute(
        text("SELECT valor FROM parametro_sistema WHERE clave = :key LIMIT 1"),
        {"key": key},
    ).scalar()
    if value is None:
        return default
    return str(value)


def _upsert_param(db: Session, key: str, value: str, description: str = "") -> None:
    db.execute(
        text(
            """
            INSERT INTO parametro_sistema (clave, valor, descripcion)
            VALUES (:key, :value, :description)
            ON DUPLICATE KEY UPDATE
                valor = VALUES(valor),
                descripcion = VALUES(descripcion)
            """
        ),
        {
            "key": key,
            "value": value,
            "description": description,
        },
    )


def _normalize_favorite_dirs(raw_dirs: list[str] | None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in raw_dirs or []:
        value = (item or "").strip()
        if not value:
            continue
        lower = value.lower()
        if lower in seen:
            continue
        seen.add(lower)
        result.append(value)
        if len(result) >= 20:
            break
    return result


def _normalize_weekdays(raw_weekdays: list[Any] | None) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for item in raw_weekdays or []:
        try:
            value = int(item)
        except (TypeError, ValueError):
            continue
        if value < 0 or value > 6:
            continue
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return sorted(result)


def get_backup_preferences(db: Session) -> dict[str, Any]:
    auto_enabled_raw = _get_param(db, PARAM_BACKUP_AUTO_ENABLED, "0")
    auto_time = _get_param(db, PARAM_BACKUP_AUTO_TIME, "02:00")
    auto_dir = _get_param(db, PARAM_BACKUP_AUTO_DIR, "").strip()
    auto_weekdays_raw = _get_param(db, PARAM_BACKUP_AUTO_WEEKDAYS, "[0,1,2,3,4,5,6]")
    favorite_dirs_raw = _get_param(db, PARAM_BACKUP_FAVORITE_DIRS, "[]")
    last_run = _get_param(db, PARAM_BACKUP_AUTO_LAST_RUN, "")
    last_status = _get_param(db, PARAM_BACKUP_AUTO_LAST_STATUS, "")
    last_message = _get_param(db, PARAM_BACKUP_AUTO_LAST_MESSAGE, "")

    try:
        auto_weekdays = json.loads(auto_weekdays_raw)
        if not isinstance(auto_weekdays, list):
            auto_weekdays = []
    except json.JSONDecodeError:
        auto_weekdays = []

    try:
        favorite_dirs = json.loads(favorite_dirs_raw)
        if not isinstance(favorite_dirs, list):
            favorite_dirs = []
    except json.JSONDecodeError:
        favorite_dirs = []

    normalized_dirs = _normalize_favorite_dirs([str(v) for v in favorite_dirs])
    if auto_dir and auto_dir not in normalized_dirs:
        normalized_dirs.insert(0, auto_dir)

    if not _is_valid_hhmm(auto_time):
        auto_time = "02:00"

    normalized_weekdays = _normalize_weekdays(auto_weekdays)
    if not normalized_weekdays:
        normalized_weekdays = [0, 1, 2, 3, 4, 5, 6]

    return {
        "auto_enabled": auto_enabled_raw in ("1", "true", "True"),
        "auto_time": auto_time,
        "auto_dir": auto_dir,
        "auto_weekdays": normalized_weekdays,
        "favorite_dirs": normalized_dirs,
        "last_run": last_run or None,
        "last_status": last_status or None,
        "last_message": last_message or None,
    }


def update_backup_preferences(
    db: Session,
    auto_enabled: bool,
    auto_time: str,
    auto_dir: str | None,
    auto_weekdays: list[int] | None,
    favorite_dirs: list[str] | None,
) -> dict[str, Any]:
    time_value = (auto_time or "").strip()
    if not _is_valid_hhmm(time_value):
        raise ValueError("Hora invalida. Use formato HH:MM")

    normalized_weekdays = _normalize_weekdays(auto_weekdays)
    if auto_enabled and not normalized_weekdays:
        raise ValueError(
            "Debe seleccionar al menos un dia para el backup automatico"
        )

    auto_dir_value = (auto_dir or "").strip()
    normalized_dirs = _normalize_favorite_dirs(favorite_dirs)
    if auto_dir_value and auto_dir_value not in normalized_dirs:
        normalized_dirs.insert(0, auto_dir_value)

    _upsert_param(
        db,
        PARAM_BACKUP_AUTO_ENABLED,
        "1" if auto_enabled else "0",
        "Habilita backup automatico programado",
    )
    _upsert_param(
        db,
        PARAM_BACKUP_AUTO_TIME,
        time_value,
        "Hora de backup automatico (HH:MM)",
    )
    _upsert_param(
        db,
        PARAM_BACKUP_AUTO_DIR,
        auto_dir_value,
        "Directorio de backup automatico",
    )
    _upsert_param(
        db,
        PARAM_BACKUP_AUTO_WEEKDAYS,
        json.dumps(normalized_weekdays, separators=(",", ":")),
        "Dias de la semana para backup automatico (0=lunes,6=domingo)",
    )
    _upsert_param(
        db,
        PARAM_BACKUP_FAVORITE_DIRS,
        json.dumps(normalized_dirs),
        "Directorios favoritos para backups",
    )
    return get_backup_preferences(db)


def record_auto_backup_result(
    db: Session,
    *,
    ok: bool,
    message: str,
    run_at_iso: str,
) -> None:
    _upsert_param(
        db,
        PARAM_BACKUP_AUTO_LAST_RUN,
        run_at_iso,
        "Fecha/hora de ultimo backup automatico",
    )
    _upsert_param(
        db,
        PARAM_BACKUP_AUTO_LAST_STATUS,
        "OK" if ok else "ERROR",
        "Estado del ultimo backup automatico",
    )
    _upsert_param(
        db,
        PARAM_BACKUP_AUTO_LAST_MESSAGE,
        message,
        "Detalle del ultimo backup automatico",
    )
