from typing import Any, Dict, List, Optional
from datetime import date
from sqlalchemy import text
from sqlalchemy.orm import Session


def _row_to_precio(row: Any) -> Dict[str, Any]:
    return {
        "id": row.id,
        "producto_id": row.producto_id,
        "producto_codigo": row.producto_codigo,
        "producto_nombre": row.producto_nombre,
        "proveedor_codigo": row.proveedor_codigo,
        "proveedor_nombre": row.proveedor_nombre,
        "fecha_precio": row.fecha_precio.isoformat() if row.fecha_precio else None,
        "precio_unitario": float(row.precio_unitario),
        "moneda": row.moneda,
        "origen": row.origen,
        "referencia_doc": row.referencia_doc,
        "notas": row.notas,
    }


def listar_precios_compra(
    db: Session,
    producto_id: Optional[int] = None,
    q: Optional[str] = None,
    proveedor: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    where = ["1=1"]
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    if producto_id is not None:
        where.append("h.producto_id = :pid")
        params["pid"] = producto_id

    if q:
        where.append(
            "(p.codigo LIKE :q OR p.nombre LIKE :q OR h.proveedor_codigo LIKE :q OR h.proveedor_nombre LIKE :q)"
        )
        params["q"] = f"%{q}%"

    if proveedor:
        where.append("(h.proveedor_codigo LIKE :prov OR h.proveedor_nombre LIKE :prov)")
        params["prov"] = f"%{proveedor}%"

    if desde is not None:
        where.append("h.fecha_precio >= :desde")
        params["desde"] = desde

    if hasta is not None:
        where.append("h.fecha_precio <= :hasta")
        params["hasta"] = hasta

    sql = text(
        """
        SELECT h.id, h.producto_id, h.proveedor_codigo, h.proveedor_nombre,
               h.fecha_precio, h.precio_unitario, h.moneda, h.origen,
               h.referencia_doc, h.notas,
               p.codigo AS producto_codigo, p.nombre AS producto_nombre
        FROM precio_compra_hist h
        JOIN producto p ON p.id = h.producto_id
        WHERE """
        + " AND ".join(where)
        + " ORDER BY h.fecha_precio DESC, h.id DESC LIMIT :limit OFFSET :offset"
    )

    rows = db.execute(sql, params).fetchall()
    return [_row_to_precio(r) for r in rows]
