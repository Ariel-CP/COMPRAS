"""Servicios para generar informes de costos de productos terminados."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from . import mbom_service
from .mbom_costos import calcular_costos
from .producto_service import listar_productos, get_producto


def _producto_por_codigo(db: Session, codigo: str) -> Optional[Dict[str, Any]]:
    row = db.execute(
        text(
            """
            SELECT id, codigo, nombre, tipo_producto, unidad_medida_id, activo
            FROM producto
            WHERE codigo = :codigo
            LIMIT 1
            """
        ),
        {"codigo": codigo},
    ).first()
    if not row:
        return None
    return {
        "id": int(row.id),
        "codigo": row.codigo,
        "nombre": row.nombre,
        "tipo_producto": row.tipo_producto,
        "unidad_medida_id": row.unidad_medida_id,
        "activo": bool(row.activo),
    }


def _formatear_resultado(
    producto: Dict[str, Any],
    cabecera: Dict[str, Any],
    costos: Dict[str, Any],
) -> Dict[str, Any]:
    materiales = costos.get("materiales", {})
    procesos = costos.get("procesos", {})
    total_materiales = float(materiales.get("total", 0) or 0)
    total_procesos = float(procesos.get("total", 0) or 0)
    total_general = float(costos.get("total", 0) or 0)
    moneda_materiales = materiales.get("moneda", "ARS")
    moneda_procesos = procesos.get("moneda", moneda_materiales)

    return {
        "producto_id": int(producto["id"]),
        "codigo": producto.get("codigo"),
        "nombre": producto.get("nombre"),
        "tipo_producto": producto.get("tipo_producto"),
        "mbom_id": int(cabecera["id"]),
        "mbom_revision": cabecera.get("revision"),
        "moneda_materiales": moneda_materiales,
        "moneda_procesos": moneda_procesos,
        "total_materiales": total_materiales,
        "total_procesos": total_procesos,
        "total_general": total_general,
        "alerta_fx": bool(costos.get("alerta_fx")),
        "detalle_alerta": costos.get("detalle_alerta"),
    }


def _costos_para_productos(
    db: Session,
    productos: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    resultados: List[Dict[str, Any]] = []
    for producto in productos:
        if not producto or producto.get("tipo_producto") != "PT":
            continue
        if not producto.get("activo", True):
            continue
        cabecera = mbom_service.get_cabecera_preferida(
            db,
            int(producto["id"]),
            "ACTIVO",
        )
        if not cabecera or not cabecera.get("id"):
            continue
        costos = calcular_costos(db, int(cabecera["id"]))
        resultados.append(_formatear_resultado(producto, cabecera, costos))
    return resultados


def listar_costos_pt(
    db: Session,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    productos = listar_productos(
        db,
        q=q,
        tipo="PT",
        activo=True,
        limit=limit,
        offset=offset,
    )
    return _costos_para_productos(db, productos)


def costos_por_productos(
    db: Session,
    producto_ids: Optional[Sequence[int]] = None,
    codigos: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    productos: List[Dict[str, Any]] = []
    vistos: set[int] = set()

    if producto_ids:
        for pid in producto_ids:
            if pid is None:
                continue
            pid_int = int(pid)
            if pid_int in vistos:
                continue
            prod = get_producto(db, pid_int)
            if prod:
                productos.append(prod)
                vistos.add(pid_int)

    if codigos:
        for codigo in codigos:
            if not codigo:
                continue
            prod = _producto_por_codigo(db, codigo.strip())
            if prod and int(prod["id"]) not in vistos:
                productos.append(prod)
                vistos.add(int(prod["id"]))

    return _costos_para_productos(db, productos)
