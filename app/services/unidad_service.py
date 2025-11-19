from typing import Any, Dict, List
from sqlalchemy import text
from sqlalchemy.orm import Session


def listar_unidades(db: Session) -> List[Dict[str, Any]]:
    rows = db.execute(
        text("SELECT id, codigo, nombre FROM unidad_medida ORDER BY codigo")
    ).fetchall()
    return [
        {"id": r.id, "codigo": r.codigo, "nombre": r.nombre}
        for r in rows
    ]
