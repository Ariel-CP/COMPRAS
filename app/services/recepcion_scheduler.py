"""
Scheduler de sincronización Access → recepcion_staging.

Ejecuta sincronizar_ciclo_completo() todos los días a las 22:00.
Sigue el mismo patrón que backup_scheduler.py (threading, sin dependencias externas).
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Optional

from sqlalchemy.exc import SQLAlchemyError

from app.db import SessionLocal
from app.services.recepcion_sync_service import sincronizar_ciclo_completo

logger = logging.getLogger(__name__)

# Hora de ejecución diaria
_SYNC_HOUR = 22
_SYNC_MINUTE = 0

_state: dict = {
    "worker_thread": None,
    "last_run_key": None,
    "last_result": None,
}
_stop_event = threading.Event()


def _tick_recepcion_sync() -> None:
    """Loop principal del worker thread. Se despierta cada 30 segundos."""
    while not _stop_event.is_set():
        now = datetime.now()
        run_key = f"{now:%Y-%m-%d} {_SYNC_HOUR:02d}:{_SYNC_MINUTE:02d}"

        if (
            now.hour == _SYNC_HOUR
            and now.minute == _SYNC_MINUTE
            and _state.get("last_run_key") != run_key
        ):
            _state["last_run_key"] = run_key
            logger.info("[SYNC SCHEDULER] Disparando sincronización diaria (%s)", run_key)

            db: Optional[object] = None
            try:
                db = SessionLocal()
                result = sincronizar_ciclo_completo(db, usuario_id=1)
                _state["last_result"] = result
                if result.get("exitoso"):
                    logger.info(
                        "[SYNC SCHEDULER] OK — nuevas=%d duplicadas=%d dur=%.1fs",
                        result.get("nuevas_insertadas", 0),
                        result.get("duplicadas", 0),
                        result.get("duracion_segundos", 0),
                    )
                else:
                    logger.error("[SYNC SCHEDULER] FALLÓ — %s", result.get("error"))
            except (OSError, SQLAlchemyError, RuntimeError, ConnectionError) as exc:
                logger.exception("[SYNC SCHEDULER] Error no capturado: %s", exc)
                _state["last_result"] = {"exitoso": False, "error": str(exc)}
            finally:
                if db is not None:
                    try:
                        db.close()
                    except Exception:
                        pass

        _stop_event.wait(30)


def start_recepcion_scheduler() -> None:
    """Inicia el thread del scheduler si no está corriendo."""
    existing: Optional[threading.Thread] = _state.get("worker_thread")
    if isinstance(existing, threading.Thread) and existing.is_alive():
        return

    _stop_event.clear()
    thread = threading.Thread(
        target=_tick_recepcion_sync,
        name="recepcion-sync-scheduler",
        daemon=True,
    )
    _state["worker_thread"] = thread
    thread.start()
    logger.info(
        "[SYNC SCHEDULER] Iniciado — sincronización diaria a las %02d:%02d",
        _SYNC_HOUR,
        _SYNC_MINUTE,
    )


def stop_recepcion_scheduler() -> None:
    """Detiene el thread del scheduler."""
    _stop_event.set()
    thread: Optional[threading.Thread] = _state.get("worker_thread")
    if isinstance(thread, threading.Thread) and thread.is_alive():
        thread.join(timeout=5)
    logger.info("[SYNC SCHEDULER] Detenido")


def get_scheduler_status() -> dict:
    """Retorna el estado actual del scheduler (para el endpoint /admin/sincronizacion/estado)."""
    thread: Optional[threading.Thread] = _state.get("worker_thread")
    activo = isinstance(thread, threading.Thread) and thread.is_alive()

    now = datetime.now()
    # Calcular próxima ejecución
    proxima_str: Optional[str] = None
    hoy_sync = now.replace(hour=_SYNC_HOUR, minute=_SYNC_MINUTE, second=0, microsecond=0)
    if now < hoy_sync:
        proxima_str = hoy_sync.isoformat()
    else:
        import datetime as dt
        manana_sync = hoy_sync.replace(day=now.day) + dt.timedelta(days=1)
        proxima_str = manana_sync.isoformat()

    return {
        "scheduler_activo": activo,
        "hora_ejecucion_diaria": f"{_SYNC_HOUR:02d}:{_SYNC_MINUTE:02d}",
        "proxima_ejecucion": proxima_str,
        "ultima_clave_run": _state.get("last_run_key"),
        "ultimo_resultado": _state.get("last_result"),
    }
