from typing import Any, Dict, List
from sqlalchemy import text
from sqlalchemy.orm import Session


def _get_costo_vigente(db: Session, producto_id: int) -> Dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT costo_unitario, moneda
            FROM costo_producto
            WHERE producto_id=:pid
              AND vigencia_desde <= CURRENT_DATE()
              AND (vigencia_hasta IS NULL OR vigencia_hasta >= CURRENT_DATE())
            ORDER BY vigencia_desde DESC
            LIMIT 1
            """
        ),
        {"pid": producto_id},
    ).first()
    if not row:
        return {"costo_unitario": 0.0, "moneda": "ARS"}
    return {"costo_unitario": float(row.costo_unitario), "moneda": row.moneda}


def calcular_costos(db: Session, mbom_id: int) -> Dict[str, Any]:
    componentes: List[Dict[str, Any]] = []
    total = 0.0
    rows = db.execute(
        text(
            """
            SELECT d.componente_producto_id AS prod_id,
                   p.codigo AS codigo, p.nombre AS nombre,
                   um.codigo AS um_codigo,
                   d.cantidad AS cantidad, d.factor_merma AS merma
            FROM mbom_detalle d
            JOIN producto p ON p.id = d.componente_producto_id
            JOIN unidad_medida um ON um.id = d.unidad_medida_id
            WHERE d.mbom_id = :mb
            ORDER BY d.renglon
            """
        ),
        {"mb": mbom_id},
    ).fetchall()
    for r in rows:
        costo_info = _get_costo_vigente(db, int(r.prod_id))
        costo_unit = costo_info["costo_unitario"]
        line_total = float(costo_unit) * float(r.cantidad)
        line_total *= (1.0 + float(r.merma))
        componentes.append(
            {
                "producto_id": int(r.prod_id),
                "codigo": r.codigo,
                "nombre": r.nombre,
                "um_codigo": r.um_codigo,
                "cantidad": float(r.cantidad),
                "factor_merma": float(r.merma),
                "costo_unitario": float(costo_unit),
                "moneda": costo_info["moneda"],
                "costo_total": line_total,
            }
        )
        total += line_total
    return {"mbom_id": mbom_id, "componentes": componentes, "total": total}
