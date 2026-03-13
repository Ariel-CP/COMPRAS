from __future__ import annotations

import logging
import threading
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError

from app.db import SessionLocal
from app.services import backup_service

logger = logging.getLogger(__name__)

_state: dict[str, threading.Thread | str | None] = {
    "worker_thread": None,
    "last_run_key": None,
}
_stop_event = threading.Event()


def _tick_auto_backup() -> None:
    while not _stop_event.is_set():
        now = datetime.now()
        try:
            db = SessionLocal()
            try:
                prefs = backup_service.get_backup_preferences(db)
                auto_enabled = bool(prefs.get("auto_enabled"))
                auto_time = str(prefs.get("auto_time") or "").strip()
                auto_dir = str(prefs.get("auto_dir") or "").strip() or None
                raw_weekdays = prefs.get("auto_weekdays") or []
                auto_weekdays = {
                    int(day)
                    for day in raw_weekdays
                    if str(day).isdigit() and 0 <= int(day) <= 6
                }

                if auto_enabled and auto_time and len(auto_time) == 5:
                    if auto_weekdays and now.weekday() not in auto_weekdays:
                        _stop_event.wait(20)
                        continue
                    run_key = f"{now:%Y-%m-%d} {auto_time}"
                    now_hhmm = now.strftime("%H:%M")
                    if now_hhmm == auto_time and _state.get("last_run_key") != run_key:
                        _state["last_run_key"] = run_key
                        try:
                            result = backup_service.create_backup(backup_dir=auto_dir)
                            filename = str(result.get("filename") or "backup.sql")
                            msg = f"Backup automatico generado: {filename}"
                            backup_service.record_auto_backup_result(
                                db,
                                ok=True,
                                message=msg,
                                run_at_iso=now.isoformat(timespec="seconds"),
                            )
                            db.commit()
                            logger.info(msg)
                        except (RuntimeError, ValueError, OSError, SQLAlchemyError) as exc:
                            msg = f"Error en backup automatico: {exc}"
                            backup_service.record_auto_backup_result(
                                db,
                                ok=False,
                                message=msg,
                                run_at_iso=now.isoformat(timespec="seconds"),
                            )
                            db.commit()
                            logger.exception(msg)
            finally:
                db.close()
        except (RuntimeError, OSError, SQLAlchemyError) as exc:
            logger.exception("Fallo en loop de scheduler de backup: %s", exc)

        _stop_event.wait(20)


def start_backup_scheduler() -> None:
    worker_thread = _state.get("worker_thread")
    if isinstance(worker_thread, threading.Thread) and worker_thread.is_alive():
        return

    _stop_event.clear()
    worker_thread = threading.Thread(
        target=_tick_auto_backup,
        name="backup-auto-scheduler",
        daemon=True,
    )
    _state["worker_thread"] = worker_thread
    worker_thread.start()
    logger.info("Scheduler de backup automatico iniciado")


def stop_backup_scheduler() -> None:
    _stop_event.set()
    worker_thread = _state.get("worker_thread")
    if isinstance(worker_thread, threading.Thread) and worker_thread.is_alive():
        worker_thread.join(timeout=3)
    _state["worker_thread"] = None
    logger.info("Scheduler de backup automatico detenido")
