from typing import Dict
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError


def db_status(db: Session) -> Dict[str, str]:
    try:
        r = db.execute(text("SELECT 1")).first()
        dbname = db.execute(text("SELECT DATABASE()"))
        dbname_val = dbname.scalar() if dbname else None
        ok = bool(r and r[0] == 1)
        return {
            "ok": "true" if ok else "false",
            "database": dbname_val or "(desconocida)",
            "message": "OK" if ok else "SIN RESPUESTA",
        }
    except SQLAlchemyError as ex:
        return {
            "ok": "false",
            "database": "(error)",
            "message": str(getattr(ex, "orig", ex)),
        }
