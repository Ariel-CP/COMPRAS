"""Jobs en memoria para importación MBOM con progreso.

Nota: el estado vive en memoria del proceso. Con `--reload` o múltiples workers,
los jobs pueden perderse.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Optional


@dataclass(slots=True)
class MBOMImportJob:
    id: str
    producto_padre_id: int
    filename: str
    estado: str = "pending"  # pending|running|done|error
    porcentaje: int = 0
    mensaje: str = ""
    error: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


_LOCK = Lock()
_JOBS: dict[str, MBOMImportJob] = {}
_TTL_SECONDS = 3 * 60 * 60  # 3h


def _cleanup_locked(now: float) -> None:
    expired: list[str] = []
    for job_id, job in _JOBS.items():
        if (now - job.updated_at) > _TTL_SECONDS:
            expired.append(job_id)
    for job_id in expired:
        _JOBS.pop(job_id, None)


def create_job(producto_padre_id: int, filename: str) -> MBOMImportJob:
    now = time.time()
    with _LOCK:
        _cleanup_locked(now)
        job_id = str(uuid.uuid4())
        job = MBOMImportJob(
            id=job_id,
            producto_padre_id=int(producto_padre_id),
            filename=filename or "",
            estado="pending",
            porcentaje=0,
            mensaje="Iniciando…",
        )
        _JOBS[job_id] = job
        return job


def get_job(job_id: str) -> Optional[MBOMImportJob]:
    now = time.time()
    with _LOCK:
        _cleanup_locked(now)
        job = _JOBS.get(job_id)
        return job


def set_running(job_id: str, porcentaje: int = 0, mensaje: str = "") -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job.estado = "running"
        job.error = None
        job.result = None
        job.porcentaje = _clamp_pct(porcentaje)
        job.mensaje = mensaje or job.mensaje
        job.updated_at = time.time()


def report(job_id: str, porcentaje: int, mensaje: str = "") -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        if job.estado not in {"pending", "running"}:
            return
        job.estado = "running"
        job.porcentaje = max(job.porcentaje, _clamp_pct(porcentaje))
        if mensaje:
            job.mensaje = mensaje
        job.updated_at = time.time()


def set_done(job_id: str, result: dict[str, Any]) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job.estado = "done"
        job.porcentaje = 100
        job.mensaje = "Completado"
        job.error = None
        job.result = result
        job.updated_at = time.time()


def set_error(job_id: str, error: str) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job.estado = "error"
        job.error = error or "Error"
        job.mensaje = "Error"
        job.updated_at = time.time()


def to_public_dict(job: MBOMImportJob) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "job_id": job.id,
        "producto_padre_id": job.producto_padre_id,
        "filename": job.filename,
        "estado": job.estado,
        "porcentaje": job.porcentaje,
        "mensaje": job.mensaje,
        "error": job.error,
    }
    if job.estado == "done":
        payload["result"] = job.result
    return payload


def _clamp_pct(value: int) -> int:
    try:
        v = int(value)
    except Exception:
        v = 0
    return 0 if v < 0 else (100 if v > 100 else v)
