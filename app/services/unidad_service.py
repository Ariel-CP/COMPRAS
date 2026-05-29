from typing import Any, Dict, List
from sqlalchemy import text
from sqlalchemy.orm import Session


def _fix_mojibake_text(value: str | None) -> str | None:
    if value is None:
        return None
    text_value = value.strip()
    if not text_value:
        return None
    if not any(marker in text_value for marker in ("Ã", "Â", "â")):
        return text_value
    try:
        repaired = text_value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text_value
    return repaired.strip() or text_value


def listar_unidades(db: Session) -> List[Dict[str, Any]]:
    rows = db.execute(
        text("SELECT id, codigo, nombre FROM unidad_medida ORDER BY codigo")
    ).fetchall()
    return [
        {
            "id": r.id,
            "codigo": _fix_mojibake_text(r.codigo),
            "nombre": _fix_mojibake_text(r.nombre),
        }
        for r in rows
    ]
