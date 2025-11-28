from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import mbom_service
from app.services.tipo_cambio_service import obtener_tasa_cercana

BASE_MONEDA = "USD"
ALERTA_MSG = (
    "Algunas líneas fueron convertidas con tasa estimada; verifique tipo de cambio."
)


def _convertir_ars_a_usd(
    db: Session,
    monto_ars: float,
    fecha: date,
) -> Dict[str, Any]:
    """Convierte ARS a USD usando la tasa cercana a la fecha de compra."""

    detalle_fx: Dict[str, Any] = {
        "tipo": "ARS->USD",
        "fecha_precio": fecha.isoformat(),
    }
    tasa = obtener_tasa_cercana(db, BASE_MONEDA, fecha, "PROMEDIO")
    if not tasa or not tasa.get("tasa"):
        detalle_fx["sin_tasa"] = True
        return {
            "valor_base": monto_ars,
            "moneda_base": "ARS",
            "detalle_fx": detalle_fx,
            "alerta": True,
        }

    valor_usd = monto_ars / float(tasa["tasa"])
    detalle_fx.update(
        {
            "tasa": float(tasa["tasa"]),
            "fecha_tasa": tasa["fecha"].isoformat(),
            "es_estimativa": bool(tasa.get("es_estimativa")),
            "origen_busqueda": tasa.get("origen_busqueda"),
        }
    )
    alerta = bool(tasa.get("es_estimativa"))
    return {
        "valor_base": valor_usd,
        "moneda_base": BASE_MONEDA,
        "detalle_fx": detalle_fx,
        "alerta": alerta,
    }


def _convertir_base_a_ars(
    db: Session,
    valor_base: float,
    moneda_base: str,
) -> Dict[str, Any]:
    """Convierte el valor base a ARS usando la tasa vigente más cercana."""

    if moneda_base == "ARS":
        return {
            "valor_ars": valor_base,
            "detalle": None,
            "alerta": False,
        }

    tasa = obtener_tasa_cercana(db, moneda_base, date.today(), "PROMEDIO")
    detalle = None
    alerta = False
    valor_convertido = valor_base
    if tasa and tasa.get("tasa"):
        valor_convertido = valor_base * float(tasa["tasa"])
        detalle = {
            "tasa": float(tasa["tasa"]),
            "fecha_tasa": tasa["fecha"].isoformat(),
            "es_estimativa": bool(tasa.get("es_estimativa")),
            "origen_busqueda": tasa.get("origen_busqueda"),
        }
        alerta = bool(tasa.get("es_estimativa"))
    else:
        alerta = True
    return {
        "valor_ars": valor_convertido,
        "detalle": detalle,
        "alerta": alerta,
    }


def _get_costo_vigente(
    db: Session,
    producto_id: int,
    memo_costos: Dict[int, Dict[str, Any]],
    en_stack: Set[int],
) -> Dict[str, Any]:
    if producto_id in memo_costos:
        return memo_costos[producto_id]

    if producto_id in en_stack:
        return {
            "valor_base": 0.0,
            "moneda_base": "ARS",
            "moneda_origen": "ARS",
            "valor_origen": 0.0,
            "fuente": "ciclo",
            "fecha_precio": None,
            "detalle_fx_hist": {"ciclo": True},
            "alerta_fx_hist": True,
        }

    en_stack.add(producto_id)
    try:
        row = db.execute(
            text(
                """
                SELECT costo_unitario, moneda, vigencia_desde
                FROM costo_producto
                                WHERE producto_id=:pid
                                    AND vigencia_desde <= CURRENT_DATE()
                                    AND (
                                            vigencia_hasta IS NULL
                                            OR vigencia_hasta >= CURRENT_DATE()
                                    )
                ORDER BY vigencia_desde DESC
                LIMIT 1
                """
            ),
            {"pid": producto_id},
        ).first()
        if row:
            data = {
                "valor_base": float(row.costo_unitario),
                "moneda_base": row.moneda,
                "moneda_origen": row.moneda,
                "valor_origen": float(row.costo_unitario),
                "fuente": "costo_producto",
                "fecha_precio": row.vigencia_desde,
                "detalle_fx_hist": None,
                "alerta_fx_hist": False,
            }
            memo_costos[producto_id] = data
            return data

        historial_row = db.execute(
            text(
                """
                SELECT precio_unitario, moneda, fecha_precio
                FROM precio_compra_hist
                WHERE producto_id = :pid
                ORDER BY fecha_precio DESC, id DESC
                LIMIT 1
                """
            ),
            {"pid": producto_id},
        ).first()
        if historial_row:
            valor_origen = float(historial_row.precio_unitario)
            moneda_origen = historial_row.moneda
            fecha_precio: date = historial_row.fecha_precio
            if moneda_origen == "ARS":
                conversion = _convertir_ars_a_usd(
                    db,
                    valor_origen,
                    fecha_precio,
                )
                data = {
                    "valor_base": conversion["valor_base"],
                    "moneda_base": conversion["moneda_base"],
                    "moneda_origen": moneda_origen,
                    "valor_origen": valor_origen,
                    "fuente": "precio_compra_hist",
                    "fecha_precio": fecha_precio,
                    "detalle_fx_hist": conversion["detalle_fx"],
                    "alerta_fx_hist": conversion["alerta"],
                }
                memo_costos[producto_id] = data
                return data
            data = {
                "valor_base": valor_origen,
                "moneda_base": moneda_origen,
                "moneda_origen": moneda_origen,
                "valor_origen": valor_origen,
                "fuente": "precio_compra_hist",
                "fecha_precio": fecha_precio,
                "detalle_fx_hist": None,
                "alerta_fx_hist": False,
            }
            memo_costos[producto_id] = data
            return data

        sub_costo = _get_costo_desde_subestructura(
            db,
            producto_id,
            memo_costos,
            en_stack,
        )
        if sub_costo:
            memo_costos[producto_id] = sub_costo
            return sub_costo

        data = {
            "valor_base": 0.0,
            "moneda_base": "ARS",
            "moneda_origen": "ARS",
            "valor_origen": 0.0,
            "fuente": "default",
            "fecha_precio": None,
            "detalle_fx_hist": None,
            "alerta_fx_hist": False,
        }
        memo_costos[producto_id] = data
        return data
    finally:
        en_stack.discard(producto_id)


def calcular_costos(db: Session, mbom_id: int) -> Dict[str, Any]:
    memo_costos: Dict[int, Dict[str, Any]] = {}
    en_stack: Set[int] = set()
    resultado = _calcular_costos_internal(
        db,
        mbom_id,
        memo_costos,
        en_stack,
    )
    alerta_fx = resultado["alerta_fx"]
    return {
        "mbom_id": mbom_id,
        "componentes": resultado["componentes"],
        "total": resultado["total"],
        "alerta_fx": alerta_fx,
        "detalle_alerta": ALERTA_MSG if alerta_fx else None,
    }


def _calcular_costos_internal(
    db: Session,
    mbom_id: int,
    memo_costos: Dict[int, Dict[str, Any]],
    en_stack: Set[int],
) -> Dict[str, Any]:
    componentes: List[Dict[str, Any]] = []
    total = 0.0
    alerta_fx_global = False
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
        costo_info = _get_costo_vigente(
            db,
            int(r.prod_id),
            memo_costos,
            en_stack,
        )
        base_valor = float(costo_info["valor_base"])
        conv_actual = _convertir_base_a_ars(
            db,
            base_valor,
            costo_info["moneda_base"],
        )
        costo_unitario_ars = conv_actual["valor_ars"]
        cantidad = float(r.cantidad)
        merma = float(r.merma)
        line_total = costo_unitario_ars * cantidad * (1.0 + merma)

        detalle_fx = {
            "hist": costo_info.get("detalle_fx_hist"),
            "display": conv_actual.get("detalle"),
            "moneda_base": costo_info["moneda_base"],
            "moneda_origen": costo_info["moneda_origen"],
        }
        if costo_info.get("fecha_precio"):
            detalle_fx["fecha_precio"] = costo_info["fecha_precio"].isoformat()

        if costo_info.get("alerta_fx_hist") or conv_actual.get("alerta"):
            alerta_fx_global = True

        componentes.append(
            {
                "producto_id": int(r.prod_id),
                "codigo": r.codigo,
                "nombre": r.nombre,
                "um_codigo": r.um_codigo,
                "cantidad": cantidad,
                "factor_merma": merma,
                "costo_unitario": costo_unitario_ars,
                "costo_unitario_usd": base_valor
                if costo_info["moneda_base"] == BASE_MONEDA
                else None,
                "moneda": "ARS",
                "fuente_costo": costo_info.get("fuente"),
                "costo_total": line_total,
                "fx_detalle": detalle_fx,
            }
        )
        total += line_total

    return {
        "componentes": componentes,
        "total": total,
        "alerta_fx": alerta_fx_global,
    }


def _get_costo_desde_subestructura(
    db: Session,
    producto_id: int,
    memo_costos: Dict[int, Dict[str, Any]],
    en_stack: Set[int],
) -> Optional[Dict[str, Any]]:
    cab = mbom_service.get_cabecera_preferida(
        db,
        producto_id,
        "ACTIVO",
    )
    if not cab:
        return None

    mbom_id = cab.get("id")
    if not mbom_id:
        return None

    sub_resultado = _calcular_costos_internal(
        db,
        int(mbom_id),
        memo_costos,
        en_stack,
    )
    total_sub = float(sub_resultado["total"])
    return {
        "valor_base": total_sub,
        "moneda_base": "ARS",
        "moneda_origen": "MBOM",
        "valor_origen": total_sub,
        "fuente": "subestructura",
        "fecha_precio": None,
        "detalle_fx_hist": {
            "mbom_id": mbom_id,
            "revision": cab.get("revision"),
        },
        "alerta_fx_hist": bool(sub_resultado["alerta_fx"]),
    }
