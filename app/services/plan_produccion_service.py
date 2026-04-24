from typing import Any, Dict, List, Optional, Set, Tuple, cast
from datetime import date

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import app.services.mbom_costos as mbom_costos
import app.services.mbom_service as mbom_service
from app.models.plan_produccion import (
    PlanProduccionCreate,
    PlanProduccionUpdate,
)


def registrar_corrida_asistente_oc(
    db: Session,
    mes: int,
    anio: int,
    usuario_id: int,
    usuario_email: str,
    usuario_nombre: Optional[str],
    persistio_sugerencias: bool,
) -> int:
    res = db.execute(
        text(
            """
            INSERT INTO asistente_oc_corrida_hist (
                anio,
                mes,
                usuario_id,
                usuario_email,
                usuario_nombre,
                persistio_sugerencias
            ) VALUES (
                :anio,
                :mes,
                :usuario_id,
                :usuario_email,
                :usuario_nombre,
                :persistio_sugerencias
            )
            """
        ),
        {
            "anio": anio,
            "mes": mes,
            "usuario_id": usuario_id,
            "usuario_email": usuario_email,
            "usuario_nombre": usuario_nombre,
            "persistio_sugerencias": 1 if persistio_sugerencias else 0,
        },
    )
    db.commit()
    last_id = res.lastrowid  # type: ignore[attr-defined]
    if not last_id:
        last_id = db.execute(text("SELECT LAST_INSERT_ID() AS id")).scalar()
    return int(last_id or 0)


def listar_corridas_asistente_oc(
    db: Session,
    mes: Optional[int] = None,
    anio: Optional[int] = None,
    limit: int = 20,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    filtros: List[str] = []
    params: Dict[str, Any] = {
        "limit": limit,
        "offset": offset,
    }

    if mes is not None:
        filtros.append("mes = :mes")
        params["mes"] = mes
    if anio is not None:
        filtros.append("anio = :anio")
        params["anio"] = anio

    where = f"WHERE {' AND '.join(filtros)}" if filtros else ""

    rows = db.execute(
        text(
            f"""
            SELECT
                id,
                anio,
                mes,
                usuario_id,
                usuario_email,
                usuario_nombre,
                persistio_sugerencias,
                fecha_corrida
            FROM asistente_oc_corrida_hist
            {where}
            ORDER BY fecha_corrida DESC, id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    total_val = db.execute(
        text(f"SELECT COUNT(*) FROM asistente_oc_corrida_hist {where}"),
        params,
    ).scalar()
    total = int(total_val or 0)

    items: List[Dict[str, Any]] = []
    for r in rows:
        fecha = r.get("fecha_corrida")
        items.append(
            {
                "id": int(r["id"]),
                "anio": int(r["anio"]),
                "mes": int(r["mes"]),
                "usuario_id": int(r["usuario_id"]),
                "usuario_email": str(r["usuario_email"] or ""),
                "usuario_nombre": str(r["usuario_nombre"] or ""),
                "persistio_sugerencias": bool(r["persistio_sugerencias"]),
                "fecha_corrida": fecha.isoformat() if fecha else None,
            }
        )

    return items, total


def _mapear_laf_activos_codigo_id(db: Session) -> Tuple[Dict[str, int], Dict[int, str]]:
    rows = db.execute(
        text(
            """
            SELECT id, codigo
            FROM producto
            WHERE tipo_producto = 'MP'
              AND activo = 1
              AND UPPER(COALESCE(rubro, '')) LIKE '%LAF%'
            """
        )
    ).fetchall()
    codigo_a_id: Dict[str, int] = {}
    id_a_codigo: Dict[int, str] = {}
    for r in rows:
        pid = int(r.id)
        codigo = str(r.codigo).strip().upper()
        codigo_a_id[codigo] = pid
        id_a_codigo[pid] = codigo
    return codigo_a_id, id_a_codigo


def listar_laf_solicitado_periodo(
    db: Session,
    mes: int,
    anio: int,
) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT s.id,
                   s.anio,
                   s.mes,
                   s.producto_id,
                   p.codigo,
                   p.nombre,
                   s.proveedor_nombre,
                   s.cantidad_total,
                   s.cantidad_q1,
                   s.cantidad_q2,
                   s.fecha_pedido,
                   s.fecha_entrega_estimada,
                   s.estado,
                   s.observaciones
            FROM asistente_oc_laf_solicitado s
            JOIN producto p ON p.id = s.producto_id
            WHERE s.anio = :anio AND s.mes = :mes
            ORDER BY s.fecha_entrega_estimada ASC, p.codigo ASC, s.id ASC
            """
        ),
        {"anio": anio, "mes": mes},
    ).fetchall()

    items: List[Dict[str, Any]] = []
    for r in rows:
        items.append(
            {
                "id": int(r.id),
                "anio": int(r.anio),
                "mes": int(r.mes),
                "producto_id": int(r.producto_id),
                "codigo": str(r.codigo),
                "nombre": str(r.nombre),
                "proveedor_nombre": str(r.proveedor_nombre),
                "cantidad_total": float(r.cantidad_total or 0.0),
                "cantidad_q1": float(r.cantidad_q1 or 0.0),
                "cantidad_q2": float(r.cantidad_q2 or 0.0),
                "fecha_pedido": r.fecha_pedido.isoformat() if r.fecha_pedido else None,
                "fecha_entrega_estimada": (
                    r.fecha_entrega_estimada.isoformat() if r.fecha_entrega_estimada else None
                ),
                "estado": str(r.estado),
                "observaciones": str(r.observaciones or ""),
            }
        )
    return items


def crear_laf_solicitado_periodo(
    db: Session,
    mes: int,
    anio: int,
    item: Dict[str, Any],
) -> Dict[str, Any]:
    codigo_a_id, id_a_codigo = _mapear_laf_activos_codigo_id(db)
    codigo = str(item.get("codigo") or "").strip().upper()
    if not codigo:
        raise ValueError("codigo es obligatorio")

    pid = codigo_a_id.get(codigo)
    if not pid:
        raise ValueError("El producto no es MP LAF activo o no existe")

    proveedor = str(item.get("proveedor_nombre") or "").strip()
    if not proveedor:
        raise ValueError("proveedor_nombre es obligatorio")

    cantidad_q1 = max(float(item.get("cantidad_q1") or 0.0), 0.0)
    cantidad_q2 = max(float(item.get("cantidad_q2") or 0.0), 0.0)
    cantidad_total_raw = item.get("cantidad_total")
    cantidad_total = (
        float(cantidad_total_raw)
        if cantidad_total_raw is not None and str(cantidad_total_raw).strip() != ""
        else (cantidad_q1 + cantidad_q2)
    )
    cantidad_total = max(cantidad_total, 0.0)

    if (cantidad_q1 + cantidad_q2) > cantidad_total:
        raise ValueError("cantidad_q1 + cantidad_q2 no puede superar cantidad_total")

    fecha_pedido = item.get("fecha_pedido") or None
    fecha_entrega_estimada = item.get("fecha_entrega_estimada") or None
    estado = str(item.get("estado") or "PENDIENTE").strip().upper()
    if estado not in {"PENDIENTE", "PARCIAL", "RECIBIDO", "CANCELADO"}:
        raise ValueError("estado inválido")
    observaciones = str(item.get("observaciones") or "").strip() or None

    res = db.execute(
        text(
            """
            INSERT INTO asistente_oc_laf_solicitado (
                anio,
                mes,
                producto_id,
                proveedor_nombre,
                cantidad_total,
                cantidad_q1,
                cantidad_q2,
                fecha_pedido,
                fecha_entrega_estimada,
                estado,
                observaciones
            ) VALUES (
                :anio,
                :mes,
                :producto_id,
                :proveedor_nombre,
                :cantidad_total,
                :cantidad_q1,
                :cantidad_q2,
                :fecha_pedido,
                :fecha_entrega_estimada,
                :estado,
                :observaciones
            )
            """
        ),
        {
            "anio": anio,
            "mes": mes,
            "producto_id": pid,
            "proveedor_nombre": proveedor,
            "cantidad_total": cantidad_total,
            "cantidad_q1": cantidad_q1,
            "cantidad_q2": cantidad_q2,
            "fecha_pedido": fecha_pedido,
            "fecha_entrega_estimada": fecha_entrega_estimada,
            "estado": estado,
            "observaciones": observaciones,
        },
    )
    db.commit()

    last_id = res.lastrowid  # type: ignore[attr-defined]
    if not last_id:
        last_id = db.execute(text("SELECT LAST_INSERT_ID() AS id")).scalar()

    return {
        "id": int(last_id or 0),
        "anio": anio,
        "mes": mes,
        "producto_id": int(pid),
        "codigo": id_a_codigo.get(pid) or codigo,
        "proveedor_nombre": proveedor,
        "cantidad_total": cantidad_total,
        "cantidad_q1": cantidad_q1,
        "cantidad_q2": cantidad_q2,
        "fecha_pedido": fecha_pedido,
        "fecha_entrega_estimada": fecha_entrega_estimada,
        "estado": estado,
        "observaciones": observaciones or "",
    }


def importar_laf_solicitado_periodo(
    db: Session,
    mes: int,
    anio: int,
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    insertados = 0
    rechazados = 0
    errores: List[str] = []

    for idx, item in enumerate(items, start=1):
        try:
            crear_laf_solicitado_periodo(db, mes, anio, item)
            insertados += 1
        except (ValueError, TypeError) as exc:
            rechazados += 1
            db.rollback()
            errores.append(f"Fila {idx}: {exc}")

    return {
        "insertados": insertados,
        "rechazados": rechazados,
        "errores": errores,
    }


def eliminar_laf_solicitado_periodo(db: Session, item_id: int) -> bool:
    existente = db.execute(
        text("SELECT id FROM asistente_oc_laf_solicitado WHERE id=:id"),
        {"id": item_id},
    ).first()
    if not existente:
        return False

    db.execute(
        text("DELETE FROM asistente_oc_laf_solicitado WHERE id=:id"),
        {"id": item_id},
    )
    db.commit()
    return True


def _obtener_solicitado_laf_por_producto_periodo(
    db: Session,
    mes: int,
    anio: int,
) -> Dict[int, float]:
    rows = db.execute(
        text(
            """
            SELECT producto_id,
                   SUM(COALESCE(cantidad_total, 0)) AS total_solicitado
            FROM asistente_oc_laf_solicitado
            WHERE anio = :anio
              AND mes = :mes
              AND estado IN ('PENDIENTE', 'PARCIAL')
            GROUP BY producto_id
            """
        ),
        {"anio": anio, "mes": mes},
    ).fetchall()

    return {int(r.producto_id): float(r.total_solicitado or 0.0) for r in rows}


def _mapear_pt_activos_codigo_id(db: Session) -> Tuple[Dict[str, int], Dict[int, str]]:
    rows = db.execute(
        text(
            """
            SELECT id, codigo
            FROM producto
            WHERE tipo_producto = 'PT' AND activo = 1
            """
        )
    ).fetchall()
    codigo_a_id: Dict[str, int] = {}
    id_a_codigo: Dict[int, str] = {}
    for r in rows:
        pid = int(r.id)
        codigo = str(r.codigo).strip().upper()
        codigo_a_id[codigo] = pid
        id_a_codigo[pid] = codigo
    return codigo_a_id, id_a_codigo


def _normalizar_fecha_corte(fecha_corte: Optional[str]) -> str:
    if not fecha_corte:
        return date.today().isoformat()
    return fecha_corte


def guardar_stock_pt_periodo(
    db: Session,
    mes: int,
    anio: int,
    fecha_corte: Optional[str],
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    codigo_a_id, id_a_codigo = _mapear_pt_activos_codigo_id(db)
    fc = _normalizar_fecha_corte(fecha_corte)

    upserts = 0
    rechazados = 0
    errores: List[str] = []
    normalizados: List[Dict[str, Any]] = []

    for idx, item in enumerate(items, start=1):
        codigo = str(item.get("codigo") or "").strip().upper()
        if not codigo:
            rechazados += 1
            errores.append(f"Fila {idx}: codigo vacío")
            continue

        pid = codigo_a_id.get(codigo)
        if not pid:
            rechazados += 1
            errores.append(f"Fila {idx}: código PT no encontrado ({codigo})")
            continue

        try:
            stock_pt = float(item.get("stock_pt") or 0.0)
        except (TypeError, ValueError):
            rechazados += 1
            errores.append(f"Fila {idx}: stock_pt inválido para {codigo}")
            continue

        stock_pt = max(stock_pt, 0.0)

        existente = db.execute(
            text(
                """
                SELECT id
                FROM asistente_oc_stock_pt_mes
                WHERE anio=:anio AND mes=:mes AND producto_id=:pid
                """
            ),
            {"anio": anio, "mes": mes, "pid": pid},
        ).first()

        if existente:
            db.execute(
                text(
                    """
                    UPDATE asistente_oc_stock_pt_mes
                    SET stock_pt=:stock_pt,
                        fecha_corte=:fecha_corte,
                        origen='IMPORT_CSV'
                    WHERE id=:id
                    """
                ),
                {
                    "id": existente.id,
                    "stock_pt": stock_pt,
                    "fecha_corte": fc,
                },
            )
        else:
            db.execute(
                text(
                    """
                    INSERT INTO asistente_oc_stock_pt_mes (
                        anio, mes, producto_id, stock_pt, fecha_corte, origen
                    ) VALUES (
                        :anio, :mes, :pid, :stock_pt, :fecha_corte, 'IMPORT_CSV'
                    )
                    """
                ),
                {
                    "anio": anio,
                    "mes": mes,
                    "pid": pid,
                    "stock_pt": stock_pt,
                    "fecha_corte": fc,
                },
            )

        normalizados.append(
            {
                "producto_id": pid,
                "codigo": id_a_codigo.get(pid) or codigo,
                "stock_pt": stock_pt,
            }
        )
        upserts += 1

    db.commit()
    return {
        "upserts": upserts,
        "rechazados": rechazados,
        "errores": errores,
        "items": normalizados,
    }


def guardar_deuda_clientes_periodo(
    db: Session,
    mes: int,
    anio: int,
    fecha_corte: Optional[str],
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    codigo_a_id, id_a_codigo = _mapear_pt_activos_codigo_id(db)
    fc = _normalizar_fecha_corte(fecha_corte)

    upserts = 0
    rechazados = 0
    errores: List[str] = []
    normalizados: List[Dict[str, Any]] = []

    for idx, item in enumerate(items, start=1):
        codigo = str(item.get("codigo") or "").strip().upper()
        if not codigo:
            rechazados += 1
            errores.append(f"Fila {idx}: codigo vacío")
            continue

        pid = codigo_a_id.get(codigo)
        if not pid:
            rechazados += 1
            errores.append(f"Fila {idx}: código PT no encontrado ({codigo})")
            continue

        try:
            deuda_clientes = float(item.get("deuda_clientes") or 0.0)
        except (TypeError, ValueError):
            rechazados += 1
            errores.append(f"Fila {idx}: deuda_clientes inválida para {codigo}")
            continue

        deuda_clientes = max(deuda_clientes, 0.0)

        existente = db.execute(
            text(
                """
                SELECT id
                FROM asistente_oc_deuda_cliente_mes
                WHERE anio=:anio AND mes=:mes AND producto_id=:pid
                """
            ),
            {"anio": anio, "mes": mes, "pid": pid},
        ).first()

        if existente:
            db.execute(
                text(
                    """
                    UPDATE asistente_oc_deuda_cliente_mes
                    SET deuda_clientes=:deuda_clientes,
                        fecha_corte=:fecha_corte,
                        origen='IMPORT_CSV'
                    WHERE id=:id
                    """
                ),
                {
                    "id": existente.id,
                    "deuda_clientes": deuda_clientes,
                    "fecha_corte": fc,
                },
            )
        else:
            db.execute(
                text(
                    """
                    INSERT INTO asistente_oc_deuda_cliente_mes (
                        anio, mes, producto_id, deuda_clientes, fecha_corte, origen
                    ) VALUES (
                        :anio, :mes, :pid, :deuda_clientes, :fecha_corte, 'IMPORT_CSV'
                    )
                    """
                ),
                {
                    "anio": anio,
                    "mes": mes,
                    "pid": pid,
                    "deuda_clientes": deuda_clientes,
                    "fecha_corte": fc,
                },
            )

        normalizados.append(
            {
                "producto_id": pid,
                "codigo": id_a_codigo.get(pid) or codigo,
                "deuda_clientes": deuda_clientes,
            }
        )
        upserts += 1

    db.commit()
    return {
        "upserts": upserts,
        "rechazados": rechazados,
        "errores": errores,
        "items": normalizados,
    }


def obtener_ajustes_pt_periodo(db: Session, mes: int, anio: int) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT p.id AS producto_id,
                   p.codigo,
                   COALESCE(s.stock_pt, 0) AS stock_pt,
                   COALESCE(d.deuda_clientes, 0) AS deuda_clientes
            FROM producto p
            LEFT JOIN asistente_oc_stock_pt_mes s
              ON s.producto_id = p.id AND s.anio = :anio AND s.mes = :mes
            LEFT JOIN asistente_oc_deuda_cliente_mes d
              ON d.producto_id = p.id AND d.anio = :anio AND d.mes = :mes
            WHERE p.tipo_producto = 'PT' AND p.activo = 1
            ORDER BY p.codigo
            """
        ),
        {"anio": anio, "mes": mes},
    ).fetchall()

    result: List[Dict[str, Any]] = []
    for r in rows:
        result.append(
            {
                "producto_id": int(r.producto_id),
                "codigo": str(r.codigo),
                "stock_pt": float(r.stock_pt or 0.0),
                "deuda_clientes": float(r.deuda_clientes or 0.0),
            }
        )
    return result


def listar_planes(
    db: Session,
    limit: int = 20,
    offset: int = 0,
    mes: Optional[int] = None,
    anio: Optional[int] = None,
    producto_id: Optional[int] = None,
) -> Tuple[List[dict], int]:
    filtros = []
    params = {}
    if mes:
        filtros.append('mes = :mes')
        params['mes'] = mes
    if anio:
        filtros.append('anio = :anio')
        params['anio'] = anio
    if producto_id:
        filtros.append('producto_id = :producto_id')
        params['producto_id'] = producto_id
    where = f"WHERE {' AND '.join(filtros)}" if filtros else ''
    sql = f"""
        SELECT p.id,
               p.producto_id,
               pr.codigo AS producto_codigo,
               pr.nombre AS producto_nombre,
               p.mes,
               p.anio,
               p.cantidad_planificada AS cantidad
        FROM plan_produccion_mensual p
        JOIN producto pr ON pr.id = p.producto_id
        {where}
        ORDER BY p.anio DESC, p.mes DESC, pr.nombre ASC
        LIMIT :limit OFFSET :offset
    """
    count_sql = f"SELECT COUNT(*) FROM plan_produccion_mensual p {where}"
    params['limit'] = limit
    params['offset'] = offset
    rows = db.execute(text(sql), params).fetchall()
    total_val = db.execute(text(count_sql), params).scalar()
    total = int(total_val or 0)
    return [dict(row) for row in rows], total


def listar_periodos_cargados(db: Session) -> List[dict]:
    """Devuelve los períodos (año/mes) que tienen planes cargados.

    Se agrupa por (anio, mes) sobre `plan_produccion_mensual`.
    """
    rows = db.execute(
        text(
            """
            SELECT
                anio,
                mes,
                COUNT(*) AS registros,
                SUM(COALESCE(cantidad_planificada, 0)) AS total_cantidad
            FROM plan_produccion_mensual
            GROUP BY anio, mes
            ORDER BY anio DESC, mes DESC
            """
        )
    ).fetchall()
    result: List[dict] = []
    for r in rows:
        result.append(
            {
                "anio": int(r.anio),
                "mes": int(r.mes),
                "registros": int(r.registros or 0),
                "total_cantidad": float(r.total_cantidad or 0),
            }
        )
    return result


def mover_periodo_plan(
    db: Session,
    desde_mes: int,
    desde_anio: int,
    hasta_mes: int,
    hasta_anio: int,
) -> Dict[str, int]:
    """Mueve todos los registros de un período de plan hacia otro período.

    Regla de seguridad: si existen productos repetidos entre origen y destino,
    se rechaza para evitar violar la unicidad (anio, mes, producto_id).
    """
    if desde_mes == hasta_mes and desde_anio == hasta_anio:
        raise ValueError("El período origen y destino no pueden ser iguales")

    origen_count_val = db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM plan_produccion_mensual
            WHERE mes = :desde_mes AND anio = :desde_anio
            """
        ),
        {"desde_mes": desde_mes, "desde_anio": desde_anio},
    ).scalar()
    origen_count = int(origen_count_val or 0)
    if origen_count == 0:
        raise ValueError("El período origen no tiene registros cargados")

    conflicto_val = db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM plan_produccion_mensual src
            JOIN plan_produccion_mensual dst
              ON dst.producto_id = src.producto_id
             AND dst.mes = :hasta_mes
             AND dst.anio = :hasta_anio
            WHERE src.mes = :desde_mes
              AND src.anio = :desde_anio
            """
        ),
        {
            "desde_mes": desde_mes,
            "desde_anio": desde_anio,
            "hasta_mes": hasta_mes,
            "hasta_anio": hasta_anio,
        },
    ).scalar()
    conflicto_count = int(conflicto_val or 0)
    if conflicto_count > 0:
        raise ValueError(
            "El período destino ya tiene productos cargados que entrarían en conflicto"
        )

    res = db.execute(
        text(
            """
            UPDATE plan_produccion_mensual
            SET mes = :hasta_mes,
                anio = :hasta_anio
            WHERE mes = :desde_mes
              AND anio = :desde_anio
            """
        ),
        {
            "desde_mes": desde_mes,
            "desde_anio": desde_anio,
            "hasta_mes": hasta_mes,
            "hasta_anio": hasta_anio,
        },
    )
    db.commit()
    actualizados = int(getattr(res, "rowcount", 0) or 0)
    return {"movidos": actualizados, "origen_registros": origen_count}


def eliminar_periodo_plan(
    db: Session,
    mes: int,
    anio: int,
) -> Dict[str, int]:
    """Elimina todos los registros de un período de plan."""
    count_val = db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM plan_produccion_mensual
            WHERE mes = :mes AND anio = :anio
            """
        ),
        {"mes": mes, "anio": anio},
    ).scalar()
    origen_count = int(count_val or 0)
    if origen_count == 0:
        raise ValueError("El período indicado no tiene registros cargados")

    res = db.execute(
        text(
            """
            DELETE FROM plan_produccion_mensual
            WHERE mes = :mes
              AND anio = :anio
            """
        ),
        {"mes": mes, "anio": anio},
    )
    db.commit()
    eliminados = int(getattr(res, "rowcount", 0) or 0)
    return {"eliminados": eliminados, "origen_registros": origen_count}


def crear_plan(db: Session, plan: PlanProduccionCreate) -> int:
    existe = db.execute(
        text(
            "SELECT 1 FROM plan_produccion_mensual "
            "WHERE producto_id=:pid AND mes=:mes AND anio=:anio"
        ),
        {"pid": plan.producto_id, "mes": plan.mes, "anio": plan.anio},
    ).first()
    if existe:
        raise ValueError("Ya existe un plan para ese producto, mes y año")
    res = db.execute(
        text(
            """
        INSERT INTO plan_produccion_mensual (producto_id, mes, anio,
        cantidad_planificada)
        VALUES (:pid, :mes, :anio, :cantidad)
    """
        ),
        {
            "pid": plan.producto_id,
            "mes": plan.mes,
            "anio": plan.anio,
            "cantidad": plan.cantidad,
        },
    )
    db.commit()
    new_id = int(getattr(res, "lastrowid", 0) or 0)
    return new_id


def actualizar_plan(db: Session, plan_id: int, plan: PlanProduccionUpdate):
    existe = db.execute(
        text(
            "SELECT id FROM plan_produccion_mensual "
            "WHERE producto_id=:pid AND mes=:mes AND anio=:anio AND id != :id"
        ),
        {
            "pid": plan.producto_id,
            "mes": plan.mes,
            "anio": plan.anio,
            "id": plan_id,
        },
    ).first()
    if existe:
        raise ValueError("Ya existe un plan para ese producto, mes y año")
    db.execute(
        text(
            """
        UPDATE plan_produccion_mensual
        SET producto_id=:pid,
            mes=:mes,
            anio=:anio,
            cantidad_planificada=:cantidad
        WHERE id=:id
    """
        ),
        {
            "pid": plan.producto_id,
            "mes": plan.mes,
            "anio": plan.anio,
            "cantidad": plan.cantidad,
            "id": plan_id,
        },
    )
    db.commit()


def eliminar_plan(db: Session, plan_id: int):
    db.execute(
        text("DELETE FROM plan_produccion_mensual WHERE id=:id"),
        {"id": plan_id},
    )
    db.commit()


def resumen_planes(db: Session, mes: int, anio: int) -> List[dict]:
    prev_mes = 12 if mes == 1 else mes - 1
    prev_anio = anio - 1 if mes == 1 else anio
    params = {
        "mes": mes,
        "anio": anio,
        "prev_mes": prev_mes,
        "prev_anio": prev_anio,
    }
    sql = text(
        """
        WITH actual AS (
            SELECT producto_id, cantidad_planificada AS cantidad
            FROM plan_produccion_mensual
            WHERE mes = :mes AND anio = :anio
        ),
        previo AS (
            SELECT producto_id, cantidad_planificada AS cantidad
            FROM plan_produccion_mensual
            WHERE mes = :prev_mes AND anio = :prev_anio
        )
        SELECT
            p.id AS producto_id,
            p.codigo,
            p.nombre,
            COALESCE(a.cantidad, 0) AS cantidad,
            COALESCE(pr.cantidad, 0) AS cantidad_prev
        FROM producto p
        LEFT JOIN actual a ON a.producto_id = p.id
        LEFT JOIN previo pr ON pr.producto_id = p.id
        WHERE p.tipo_producto = 'PT' AND p.activo = 1
        ORDER BY p.nombre ASC
        """
    )
    rows = db.execute(sql, params).fetchall()
    result = []
    for row in rows:
        cantidad = float(row.cantidad or 0)
        prev = float(row.cantidad_prev or 0)
        var_abs = cantidad - prev
        var_pct = None if prev == 0 else (var_abs / prev) * 100
        result.append(
            {
                "producto_id": int(row.producto_id),
                "codigo": row.codigo,
                "nombre": row.nombre,
                "cantidad": cantidad,
                "cantidad_prev": prev,
                "variacion_abs": var_abs,
                "variacion_pct": var_pct,
            }
        )
    return result


def resumen_rango_planes(
    db: Session,
    desde_mes: int,
    desde_anio: int,
    hasta_mes: int,
    hasta_anio: int,
) -> dict:
    """
    Devuelve series de variaciones por producto en un rango de meses (máx 12).
    """
    start_ord = desde_anio * 12 + desde_mes
    end_ord = hasta_anio * 12 + hasta_mes
    if end_ord < start_ord:
        raise ValueError("El rango 'hasta' debe ser mayor o igual a 'desde'.")
    # Máximo 12 meses para mantener respuesta liviana
    max_span = 12
    span = (hasta_anio - desde_anio) * 12 + (hasta_mes - desde_mes) + 1
    if span > max_span:
        raise ValueError(f"El rango no puede exceder {max_span} meses.")

    # Armar lista de períodos en orden
    periodos = []
    cur_anio, cur_mes = desde_anio, desde_mes
    for _ in range(span):
        periodos.append(
            {
                "anio": cur_anio,
                "mes": cur_mes,
                "label": f"{cur_anio}-{cur_mes:02d}",
                "ord": cur_anio * 12 + cur_mes,
            }
        )
        if cur_mes == 12:
            cur_mes = 1
            cur_anio += 1
        else:
            cur_mes += 1

    # Traer datos de plan dentro del rango
    sql = text(
        """
         SELECT ppm.producto_id,
             p.codigo,
             p.nombre,
             ppm.anio,
             ppm.mes,
             ppm.cantidad_planificada
        FROM plan_produccion_mensual ppm
        JOIN producto p ON p.id = ppm.producto_id
        WHERE p.tipo_producto = 'PT' AND p.activo = 1
          AND ((ppm.anio * 12 + ppm.mes) BETWEEN :start_ord AND :end_ord)
        ORDER BY ppm.anio, ppm.mes
        """
    )
    rows = db.execute(
        sql, {"start_ord": start_ord, "end_ord": end_ord}
    ).fetchall()

    productos: dict[int, dict] = {}
    for row in rows:
        pid = int(row.producto_id)
        prod = productos.setdefault(
            pid,
            {
                "producto_id": pid,
                "codigo": row.codigo,
                "nombre": row.nombre,
                "cantidades": {},
            },
        )
        ord_key = row.anio * 12 + row.mes
        prod["cantidades"][ord_key] = float(row.cantidad_planificada or 0)

    series = []
    resumen_netos = []
    for pid, prod in productos.items():
        puntos = []
        prev_cant = 0.0
        primera_cant = None
        ultima_cant = None
        for per in periodos:
            ord_key = per["ord"]
            cant = float(prod["cantidades"].get(ord_key, 0.0))
            if primera_cant is None:
                primera_cant = cant
            ultima_cant = cant
            var_abs = cant - prev_cant
            var_pct = None if prev_cant == 0 else (var_abs / prev_cant) * 100
            puntos.append(
                {
                    "anio": per["anio"],
                    "mes": per["mes"],
                    "periodo": per["label"],
                    "cantidad": cant,
                    "variacion_abs": var_abs,
                    "variacion_pct": var_pct,
                }
            )
            prev_cant = cant
        neto_abs = (ultima_cant or 0) - (primera_cant or 0)
        neto_pct = None
        if primera_cant:
            neto_pct = (neto_abs / primera_cant) * 100
        series.append(
            {
                "producto_id": pid,
                "codigo": prod["codigo"],
                "nombre": prod["nombre"],
                "puntos": puntos,
                "neto_abs": neto_abs,
                "neto_pct": neto_pct,
            }
        )
        resumen_netos.append(
            {
                "producto_id": pid,
                "codigo": prod["codigo"],
                "nombre": prod["nombre"],
                "neto_abs": neto_abs,
                "neto_pct": neto_pct,
            }
        )

    top_suben = sorted(
        [r for r in resumen_netos if r["neto_abs"] > 0],
        key=lambda x: x["neto_abs"],
        reverse=True,
    )[:10]
    top_bajan = sorted(
        [r for r in resumen_netos if r["neto_abs"] < 0],
        key=lambda x: x["neto_abs"],
    )[:10]

    return {
        "periodos": [
            {"anio": p["anio"], "mes": p["mes"], "label": p["label"]}
            for p in periodos
        ],
        "series": series,
        "top_suben": top_suben,
        "top_bajan": top_bajan,
    }


def _expandir_componentes(
    db: Session,
    producto_id: int,
    cantidad_requerida: float,
    visitados: Set[int],
    alertas: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Explota recursivamente el MBOM activo para obtener componentes hoja.

    - Multiplica cantidades por la cantidad requerida del PT/WIP origen.
        - Si un componente es WIP/PT, intenta expandir; si no hay MBOM, se
            considera hoja.
    - Evita ciclos usando el set visitados.
    """

    if producto_id in visitados:
        if alertas is not None:
            alertas.append(
                f"Ciclo detectado en estructura MBOM para producto_id={producto_id}."
            )
        return []
    visitados.add(producto_id)

    cab = mbom_service.get_cabecera_preferida(db, producto_id, "ACTIVO")
    if not cab:
        visitados.discard(producto_id)
        return []

    mbom_id = cab.get("id")
    if not mbom_id:
        visitados.discard(producto_id)
        return []

    rows = db.execute(
        text(
            """
            SELECT d.componente_producto_id AS comp_id,
                   p.codigo AS codigo,
                   p.nombre AS nombre,
                   p.tipo_producto AS tipo_producto,
                   p.activo AS activo,
                   d.unidad_medida_id AS um_id,
                   um.codigo AS um_codigo,
                   d.cantidad AS cantidad,
                   d.factor_merma AS merma
            FROM mbom_detalle d
            JOIN producto p ON p.id = d.componente_producto_id
            JOIN unidad_medida um ON um.id = d.unidad_medida_id
            WHERE d.mbom_id = :mb
            ORDER BY d.renglon
            """
        ),
        {"mb": mbom_id},
    ).fetchall()

    componentes: List[Dict[str, Any]] = []
    for r in rows:
        cantidad_linea = cantidad_requerida * float(r.cantidad)
        cantidad_linea *= 1.0 + float(r.merma or 0)
        tipo = r.tipo_producto
        comp_id = int(r.comp_id)

        if tipo in ("WIP", "PT"):
            sub_componentes = _expandir_componentes(
                db,
                comp_id,
                cantidad_linea,
                visitados,
                alertas,
            )
            if sub_componentes:
                componentes.extend(sub_componentes)
                continue

        componentes.append(
            {
                "producto_id": comp_id,
                "codigo": r.codigo,
                "nombre": r.nombre,
                "activo": bool(r.activo),
                "unidad_medida_id": int(r.um_id),
                "um_codigo": r.um_codigo,
                "cantidad": cantidad_linea,
            }
        )

    visitados.discard(producto_id)
    return componentes


def _costo_vigente_seguro(
    db: Session,
    producto_id: int,
    memo_costos: Dict[int, Dict[str, Any]],
    en_stack: Set[int],
) -> Dict[str, Any]:
    """Wrapper que oculta la llamada protegida al servicio de costos."""

    return mbom_costos._get_costo_vigente(  # noqa: SLF001
        db,
        producto_id,
        memo_costos,
        en_stack,
    )


def _convertir_base_a_ars_seguro(
    db: Session, valor_base: float, moneda_base: str
) -> Dict[str, Any]:
    """Wrapper que oculta la llamada protegida a conversión FX."""

    return mbom_costos._convertir_base_a_ars(  # noqa: SLF001
        db,
        valor_base,
        moneda_base,
    )


def _normalizar_fuente(fuente: Optional[str], valor_base: float) -> str:
    fuente_low = (fuente or "").lower()
    if fuente_low == "costo_producto":
        return "COSTO_PRODUCTO"
    if fuente_low == "precio_compra_hist":
        return "PRECIO_COMPRA"
    if fuente_low in {"default", "ciclo"}:
        return "SIN_PRECIO"
    if not fuente and valor_base > 0:
        return "SUB_MBOM"
    return "SIN_PRECIO"


def calcular_requerimientos_valorizados(
    db: Session,
    mes: int,
    anio: int,
    persistir: bool = False,
) -> Dict[str, Any]:
    """Calcula requerimientos del plan mensual con valoración USD/ARS.

    - Usa MBOM activo de cada PT del plan.
    - Valoriza con último costo/precio (mbom_costos) y FX vigente.
    - Si persistir=True, upsert en requerimiento_material_mensual.
    """

    planes = db.execute(
        text(
            """
            SELECT ppm.producto_id,
                   ppm.cantidad_planificada,
                   p.codigo,
                   p.nombre
            FROM plan_produccion_mensual ppm
            JOIN producto p ON p.id = ppm.producto_id
            WHERE ppm.mes = :mes AND ppm.anio = :anio
              AND p.tipo_producto = 'PT' AND p.activo = 1
            """
        ),
        {"mes": mes, "anio": anio},
    ).fetchall()

    if not planes:
        return {
            "items": [],
            "total_ars": 0.0,
            "total_usd": 0.0,
            "persistidos": 0,
            "alerta_fx": False,
        }

    acumulados: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for plan_row in planes:
        visitados: Set[int] = set()
        componentes = _expandir_componentes(
            db,
            int(plan_row.producto_id),
            float(plan_row.cantidad_planificada or 0),
            visitados,
        )
        for comp in componentes:
            key = (comp["producto_id"], comp["unidad_medida_id"])
            actual = acumulados.get(key)
            if actual:
                actual["cantidad"] += comp["cantidad"]
                actual["activo"] = actual["activo"] and bool(
                    comp.get("activo", True)
                )
            else:
                acumulados[key] = {
                    "producto_id": comp["producto_id"],
                    "codigo": comp["codigo"],
                    "nombre": comp["nombre"],
                    "unidad_medida_id": comp["unidad_medida_id"],
                    "um_codigo": comp["um_codigo"],
                    "activo": bool(comp.get("activo", True)),
                    "cantidad": comp["cantidad"],
                }

    memo_costos: Dict[int, Dict[str, Any]] = {}
    en_stack: Set[int] = set()
    items: List[Dict[str, Any]] = []
    total_ars = 0.0
    total_usd = 0.0
    persistidos = 0
    alerta_fx_global = False

    for comp in acumulados.values():
        costo_info = _costo_vigente_seguro(
            db,
            comp["producto_id"],
            memo_costos,
            en_stack,
        )
        valor_base = float(costo_info.get("valor_base") or 0.0)
        moneda_base = costo_info.get("moneda_base") or mbom_costos.BASE_MONEDA
        conv_actual = _convertir_base_a_ars_seguro(
            db,
            valor_base,
            moneda_base,
        )

        precio_unit_usd = None
        if moneda_base == mbom_costos.BASE_MONEDA:
            precio_unit_usd = valor_base
        precio_unit_ars = float(conv_actual.get("valor_ars") or 0.0)
        cantidad = float(comp.get("cantidad") or 0.0)
        total_item_ars = precio_unit_ars * cantidad
        total_item_usd = (
            precio_unit_usd * cantidad if precio_unit_usd is not None else None
        )

        if total_item_ars:
            total_ars += total_item_ars
        if total_item_usd is not None:
            total_usd += total_item_usd

        alerta_fx = bool(
            costo_info.get("alerta_fx_hist") or conv_actual.get("alerta")
        )
        alerta_fx_global = alerta_fx_global or alerta_fx

        detalle_fx = conv_actual.get("detalle") or {}
        fx_tasa = detalle_fx.get("tasa") if isinstance(detalle_fx, dict) else None
        fx_es_estimativa = None
        if isinstance(detalle_fx, dict):
            fx_es_estimativa = detalle_fx.get("es_estimativa")

        fuente_norm = _normalizar_fuente(costo_info.get("fuente"), valor_base)

        item = {
            "producto_id": comp["producto_id"],
            "codigo": comp["codigo"],
            "nombre": comp["nombre"],
            "unidad_medida_id": comp["unidad_medida_id"],
            "um_codigo": comp["um_codigo"],
            "activo": bool(comp.get("activo", True)),
            "cantidad": cantidad,
            "precio_unit_usd": precio_unit_usd,
            "precio_unit_ars": precio_unit_ars,
            "total_usd": total_item_usd,
            "total_ars": total_item_ars,
            "fuente": fuente_norm,
            "moneda_origen": costo_info.get("moneda_origen"),
            "fecha_precio": costo_info.get("fecha_precio"),
            "fx_tasa_usd_ars": fx_tasa,
            "fx_es_estimativa": fx_es_estimativa,
            "alerta_fx": alerta_fx,
        }
        items.append(item)

        if persistir:
            params = {
                "anio": anio,
                "mes": mes,
                "comp_id": comp["producto_id"],
                "um_id": comp["unidad_medida_id"],
                "cant": cantidad,
                "costo_fuente": fuente_norm,
                "costo_unit_usd": precio_unit_usd,
                "costo_unit_ars": precio_unit_ars,
                "total_usd": total_item_usd,
                "total_ars": total_item_ars,
                "moneda_origen": costo_info.get("moneda_origen"),
                "fecha_precio": costo_info.get("fecha_precio"),
                "fx_usd_ars": fx_tasa,
                "fx_es_estimativa": fx_es_estimativa,
            }
            existente = db.execute(
                text(
                    """
                        SELECT id FROM requerimiento_material_mensual
                        WHERE anio=:anio AND mes=:mes
                            AND componente_producto_id=:comp_id
                            AND unidad_medida_id=:um_id
                    """
                ),
                params,
            ).first()
            if existente:
                db.execute(
                    text(
                        """
                        UPDATE requerimiento_material_mensual
                        SET cantidad_calculada=:cant,
                            costo_fuente=:costo_fuente,
                            costo_unitario_usd=:costo_unit_usd,
                            costo_unitario_ars=:costo_unit_ars,
                            total_usd=:total_usd,
                            total_ars=:total_ars,
                            moneda_origen=:moneda_origen,
                            fecha_precio=:fecha_precio,
                            fx_usd_ars=:fx_usd_ars,
                            fx_es_estimativa=:fx_es_estimativa,
                            origen='CALCULADO',
                            fecha_calculo=CURRENT_TIMESTAMP
                        WHERE id=:id
                        """
                    ),
                    {**params, "id": existente.id},
                )
            else:
                db.execute(
                    text(
                        """
                        INSERT INTO requerimiento_material_mensual (
                            anio, mes, componente_producto_id, unidad_medida_id,
                            cantidad_calculada, costo_fuente, costo_unitario_usd,
                            costo_unitario_ars, total_usd, total_ars, moneda_origen,
                            fecha_precio, fx_usd_ars, fx_es_estimativa, origen
                        ) VALUES (
                            :anio, :mes, :comp_id, :um_id,
                            :cant, :costo_fuente, :costo_unit_usd,
                            :costo_unit_ars, :total_usd, :total_ars, :moneda_origen,
                            :fecha_precio, :fx_usd_ars, :fx_es_estimativa,
                            'CALCULADO'
                        )
                        """
                    ),
                    params,
                )
            persistidos += 1

    if persistir:
        db.commit()

    return {
        "items": items,
        "total_ars": total_ars,
        "total_usd": total_usd,
        "persistidos": persistidos,
        "alerta_fx": alerta_fx_global,
    }


def _obtener_stock_periodo(
    db: Session,
    mes: int,
    anio: int,
) -> Dict[int, Dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT producto_id, stock_disponible, fecha_corte, origen
            FROM stock_disponible_mes
            WHERE mes=:mes AND anio=:anio
            """
        ),
        {"mes": mes, "anio": anio},
    ).fetchall()

    stock_map: Dict[int, Dict[str, Any]] = {}
    for row in rows:
        stock_map[int(row.producto_id)] = {
            "stock_disponible": float(row.stock_disponible or 0),
            "fecha_corte": (
                row.fecha_corte.isoformat() if row.fecha_corte else None
            ),
            "origen": row.origen,
        }
    return stock_map


def _periodo_anterior(mes: int, anio: int) -> Tuple[int, int]:
    if mes == 1:
        return 12, anio - 1
    return mes - 1, anio


def _obtener_planes_pt_periodo(
    db: Session,
    mes: int,
    anio: int,
) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT ppm.producto_id,
                   ppm.cantidad_planificada,
                   p.codigo,
                   p.nombre
            FROM plan_produccion_mensual ppm
            JOIN producto p ON p.id = ppm.producto_id
            WHERE ppm.mes = :mes AND ppm.anio = :anio
              AND p.tipo_producto = 'PT' AND p.activo = 1
            ORDER BY ppm.cantidad_planificada DESC, p.codigo ASC
            """
        ),
        {"mes": mes, "anio": anio},
    ).fetchall()

    planes: List[Dict[str, Any]] = []
    for row in rows:
        planes.append(
            {
                "producto_id": int(row.producto_id),
                "codigo": row.codigo,
                "nombre": row.nombre,
                "cantidad_planificada": float(row.cantidad_planificada or 0.0),
            }
        )
    return planes


def _requerimientos_por_plan_priorizados(
    db: Session,
    planes: List[Dict[str, Any]],
    alertas: List[str],
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for idx, plan in enumerate(planes, start=1):
        componentes_raw = _expandir_componentes(
            db,
            int(plan["producto_id"]),
            float(plan.get("cantidad_planificada") or 0.0),
            set(),
            alertas,
        )

        componentes_agg: Dict[Tuple[int, int], Dict[str, Any]] = {}
        for comp in componentes_raw:
            key = (int(comp["producto_id"]), int(comp["unidad_medida_id"]))
            actual = componentes_agg.get(key)
            if actual:
                actual["cantidad_requerida"] += float(comp.get("cantidad") or 0.0)
                actual["activo"] = actual["activo"] and bool(comp.get("activo", True))
            else:
                componentes_agg[key] = {
                    "producto_id": int(comp["producto_id"]),
                    "codigo": comp["codigo"],
                    "nombre": comp["nombre"],
                    "unidad_medida_id": int(comp["unidad_medida_id"]),
                    "um_codigo": comp["um_codigo"],
                    "activo": bool(comp.get("activo", True)),
                    "cantidad_requerida": float(comp.get("cantidad") or 0.0),
                }

        items.append(
            {
                "prioridad": idx,
                "producto_plan_id": int(plan["producto_id"]),
                "producto_plan_codigo": plan["codigo"],
                "producto_plan_nombre": plan["nombre"],
                "cantidad_presunta": float(plan.get("cantidad_planificada") or 0.0),
                "componentes": list(componentes_agg.values()),
            }
        )

    return items


def _calcular_faltantes_priorizados_para_planes(
    db: Session,
    planes: List[Dict[str, Any]],
    mes_stock: int,
    anio_stock: int,
    alertas: List[str],
) -> Dict[str, Any]:
    if not planes:
        return {
            "faltantes_items": [],
            "total_requerido": 0.0,
            "total_stock_considerado": 0.0,
            "total_faltante": 0.0,
            "faltantes_sin_stock": 0,
            "detalle_prioridades": [],
            "stock_map": {},
        }

    stock_map = _obtener_stock_periodo(db, mes_stock, anio_stock)
    stock_remanente: Dict[int, float] = {
        int(pid): float(data.get("stock_disponible") or 0.0)
        for pid, data in stock_map.items()
    }

    faltantes_sin_stock = 0
    acumulado: Dict[Tuple[int, int], Dict[str, Any]] = {}
    detalle_prioridades: List[Dict[str, Any]] = []
    requerimientos_plan = _requerimientos_por_plan_priorizados(db, planes, alertas)

    for req_plan in requerimientos_plan:
        detalle_comp: List[Dict[str, Any]] = []
        for comp in req_plan["componentes"]:
            comp_id = int(comp["producto_id"])
            um_id = int(comp["unidad_medida_id"])
            key = (comp_id, um_id)

            requerido = float(comp.get("cantidad_requerida") or 0.0)
            stock_info = stock_map.get(comp_id)
            stock_antes = float(stock_remanente.get(comp_id, 0.0))
            asignado = min(requerido, stock_antes)
            faltante = max(0.0, requerido - asignado)
            stock_despues = max(0.0, stock_antes - asignado)
            stock_remanente[comp_id] = stock_despues

            if stock_info is None and requerido > 0:
                faltantes_sin_stock += 1

            actual = acumulado.get(key)
            if actual:
                actual["cantidad_requerida"] += requerido
                actual["stock_asignado"] += asignado
                actual["faltante"] += faltante
                actual["activo"] = actual["activo"] and bool(comp.get("activo", True))
            else:
                stock_inicial = (
                    float(stock_info.get("stock_disponible") or 0.0)
                    if stock_info
                    else 0.0
                )
                acumulado[key] = {
                    "producto_id": comp_id,
                    "codigo": comp["codigo"],
                    "nombre": comp["nombre"],
                    "unidad_medida_id": um_id,
                    "um_codigo": comp["um_codigo"],
                    "activo": bool(comp.get("activo", True)),
                    "cantidad_requerida": requerido,
                    "stock_disponible": stock_inicial,
                    "stock_asignado": asignado,
                    "faltante": faltante,
                    "fecha_corte_stock": (
                        stock_info.get("fecha_corte") if stock_info else None
                    ),
                    "origen_stock": stock_info.get("origen") if stock_info else None,
                }

            detalle_comp.append(
                {
                    "componente_id": comp_id,
                    "componente_codigo": comp["codigo"],
                    "componente_nombre": comp["nombre"],
                    "um_codigo": comp["um_codigo"],
                    "requerido": requerido,
                    "stock_antes": stock_antes,
                    "stock_asignado": asignado,
                    "faltante": faltante,
                    "stock_despues": stock_despues,
                }
            )

        detalle_prioridades.append(
            {
                "prioridad": int(req_plan["prioridad"]),
                "producto_plan_id": int(req_plan["producto_plan_id"]),
                "producto_plan_codigo": req_plan["producto_plan_codigo"],
                "producto_plan_nombre": req_plan["producto_plan_nombre"],
                "cantidad_presunta": float(req_plan["cantidad_presunta"]),
                "componentes": detalle_comp,
            }
        )

    faltantes_items: List[Dict[str, Any]] = []
    total_requerido = 0.0
    total_stock_considerado = 0.0
    total_faltante = 0.0

    for item in acumulado.values():
        requerido = float(item["cantidad_requerida"])
        stock_asignado = float(item["stock_asignado"])
        cobertura = 100.0
        if requerido > 0:
            cobertura = min((stock_asignado / requerido) * 100, 100.0)

        item["cobertura_pct"] = cobertura
        faltantes_items.append(item)

        total_requerido += requerido
        total_stock_considerado += float(item["stock_disponible"])
        total_faltante += float(item["faltante"])

        if bool(item.get("activo", True)) is False:
            alertas.append(
                f"El componente {item['codigo']} está inactivo y participa en la estructura."
            )

    return {
        "faltantes_items": faltantes_items,
        "total_requerido": total_requerido,
        "total_stock_considerado": total_stock_considerado,
        "total_faltante": total_faltante,
        "faltantes_sin_stock": faltantes_sin_stock,
        "detalle_prioridades": detalle_prioridades,
        "stock_map": stock_map,
    }


def _calcular_faltantes_priorizados(
    db: Session,
    mes_plan: int,
    anio_plan: int,
    mes_stock: int,
    anio_stock: int,
    alertas: List[str],
) -> Dict[str, Any]:
    planes = _obtener_planes_pt_periodo(db, mes_plan, anio_plan)
    return _calcular_faltantes_priorizados_para_planes(
        db,
        planes,
        mes_stock,
        anio_stock,
        alertas,
    )


def _persistir_sugerencias_compra(
    db: Session,
    mes: int,
    anio: int,
    faltantes_items: List[Dict[str, Any]],
    alertas: List[str],
) -> Dict[str, int]:
    upserts = 0
    eliminados = 0

    for item in faltantes_items:
        producto_id = int(item["producto_id"])
        unidad_medida_id = int(item["unidad_medida_id"])
        faltante = float(item["faltante"])

        existente = db.execute(
            text(
                """
                SELECT id, estado
                FROM sugerencia_compra
                WHERE anio=:anio AND mes=:mes
                  AND producto_id=:producto_id
                  AND unidad_medida_id=:unidad_medida_id
                """
            ),
            {
                "anio": anio,
                "mes": mes,
                "producto_id": producto_id,
                "unidad_medida_id": unidad_medida_id,
            },
        ).first()

        if faltante > 0:
            params = {
                "anio": anio,
                "mes": mes,
                "producto_id": producto_id,
                "unidad_medida_id": unidad_medida_id,
                "cantidad_necesaria": float(item["cantidad_requerida"]),
                "stock_disponible": float(item["stock_disponible"]),
                "cantidad_sugerida": faltante,
                "motivo": "Generado por análisis de faltantes del plan.",
            }
            if existente:
                if existente.estado == "APROBADA":
                    alertas.append(
                        "La sugerencia aprobada de "
                        f"{item['codigo']} no se cambió de estado."
                    )
                    db.execute(
                        text(
                            """
                            UPDATE sugerencia_compra
                            SET cantidad_necesaria=:cantidad_necesaria,
                                stock_disponible=:stock_disponible,
                                cantidad_sugerida=:cantidad_sugerida,
                                motivo=:motivo
                            WHERE id=:id
                            """
                        ),
                        {**params, "id": existente.id},
                    )
                else:
                    db.execute(
                        text(
                            """
                            UPDATE sugerencia_compra
                            SET cantidad_necesaria=:cantidad_necesaria,
                                stock_disponible=:stock_disponible,
                                cantidad_sugerida=:cantidad_sugerida,
                                estado='PENDIENTE',
                                motivo=:motivo
                            WHERE id=:id
                            """
                        ),
                        {**params, "id": existente.id},
                    )
            else:
                db.execute(
                    text(
                        """
                        INSERT INTO sugerencia_compra (
                            anio, mes, producto_id, unidad_medida_id,
                            cantidad_necesaria, stock_disponible,
                            cantidad_sugerida, estado, motivo
                        ) VALUES (
                            :anio, :mes, :producto_id, :unidad_medida_id,
                            :cantidad_necesaria, :stock_disponible,
                            :cantidad_sugerida, 'PENDIENTE', :motivo
                        )
                        """
                    ),
                    params,
                )
            upserts += 1
            continue

        if existente and existente.estado != "APROBADA":
            db.execute(
                text("DELETE FROM sugerencia_compra WHERE id=:id"),
                {"id": existente.id},
            )
            eliminados += 1

    return {"upserts": upserts, "eliminados": eliminados}


def _calcular_capacidad_por_stock(
    db: Session,
    mes: int,
    anio: int,
    stock_map: Dict[int, Dict[str, Any]],
    alertas: List[str],
) -> List[Dict[str, Any]]:
    planes = _obtener_planes_pt_periodo(db, mes, anio)

    return _calcular_capacidad_por_stock_para_planes(
        db,
        planes,
        stock_map,
        alertas,
    )


def _calcular_capacidad_por_stock_para_planes(
    db: Session,
    planes: List[Dict[str, Any]],
    stock_map: Dict[int, Dict[str, Any]],
    alertas: List[str],
) -> List[Dict[str, Any]]:

    capacidad_items: List[Dict[str, Any]] = []
    for row in planes:
        producto_id = int(row["producto_id"])
        mbom = mbom_service.get_cabecera_preferida(db, producto_id, "ACTIVO")
        if not mbom:
            alertas.append(
                "No hay MBOM activa vigente para "
                f"{row['codigo']}; no se puede calcular capacidad."
            )
            capacidad_items.append(
                {
                    "producto_id": producto_id,
                    "codigo": row["codigo"],
                    "nombre": row["nombre"],
                    "cantidad_planificada": float(row.get("cantidad_planificada") or 0),
                    "max_fabricable": 0.0,
                    "max_fabricable_entero": 0,
                    "faltante_pt": float(row.get("cantidad_planificada") or 0),
                    "cobertura_plan_pct": 0.0,
                    "componente_limitante": None,
                }
            )
            continue

        comp_unitarios = _expandir_componentes(
            db,
            producto_id,
            1.0,
            set(),
            alertas,
        )
        if not comp_unitarios:
            alertas.append(
                "La estructura MBOM de "
                f"{row['codigo']} no tiene componentes hoja para calcular capacidad."
            )
            capacidad_items.append(
                {
                    "producto_id": producto_id,
                    "codigo": row["codigo"],
                    "nombre": row["nombre"],
                    "cantidad_planificada": float(row.get("cantidad_planificada") or 0),
                    "max_fabricable": 0.0,
                    "max_fabricable_entero": 0,
                    "faltante_pt": float(row.get("cantidad_planificada") or 0),
                    "cobertura_plan_pct": 0.0,
                    "componente_limitante": None,
                }
            )
            continue

        comp_por_pt: Dict[int, Dict[str, Any]] = {}
        for comp in comp_unitarios:
            comp_id = int(comp["producto_id"])
            actual = comp_por_pt.get(comp_id)
            if actual:
                actual["cantidad_por_pt"] += float(comp["cantidad"])
            else:
                comp_por_pt[comp_id] = {
                    "producto_id": comp_id,
                    "codigo": comp["codigo"],
                    "nombre": comp["nombre"],
                    "um_codigo": comp["um_codigo"],
                    "cantidad_por_pt": float(comp["cantidad"]),
                }

        max_fabricable = None
        limitante: Optional[Dict[str, Any]] = None
        for comp in comp_por_pt.values():
            consumo = float(comp["cantidad_por_pt"])
            if consumo <= 0:
                continue

            stock = float(
                (stock_map.get(comp["producto_id"]) or {}).get(
                    "stock_disponible",
                    0.0,
                )
            )
            fabricable_comp = stock / consumo
            if max_fabricable is None or fabricable_comp < max_fabricable:
                max_fabricable = fabricable_comp
                limitante = {
                    "producto_id": comp["producto_id"],
                    "codigo": comp["codigo"],
                    "nombre": comp["nombre"],
                    "um_codigo": comp["um_codigo"],
                    "stock_disponible": stock,
                    "consumo_por_pt": consumo,
                    "max_fabricable_por_componente": fabricable_comp,
                }

        max_fabricable_val = float(max_fabricable or 0.0)
        max_fabricable_entero = int(max_fabricable_val) if max_fabricable_val > 0 else 0
        planificado = float(row.get("cantidad_planificada") or 0.0)
        faltante_pt = max(0.0, planificado - max_fabricable_entero)
        cobertura = 0.0 if planificado <= 0 else (max_fabricable_entero / planificado) * 100

        capacidad_items.append(
            {
                "producto_id": producto_id,
                "codigo": row["codigo"],
                "nombre": row["nombre"],
                "cantidad_planificada": planificado,
                "max_fabricable": max_fabricable_val,
                "max_fabricable_entero": max_fabricable_entero,
                "faltante_pt": faltante_pt,
                "cobertura_plan_pct": min(cobertura, 100.0),
                "componente_limitante": limitante,
            }
        )

    return capacidad_items


def _limpiar_alertas(alertas: List[str]) -> List[str]:
    alertas_limpias: List[str] = []
    seen = set()
    for alerta in alertas:
        alerta_txt = str(alerta or "").strip()
        if not alerta_txt or alerta_txt in seen:
            continue
        seen.add(alerta_txt)
        alertas_limpias.append(alerta_txt)
    return alertas_limpias


def calcular_faltantes_y_capacidad(
    db: Session,
    mes: int,
    anio: int,
    persistir_sugerencias: bool = True,
) -> Dict[str, Any]:
    mes_stock, anio_stock = _periodo_anterior(mes, anio)
    alertas: List[str] = []

    calc = _calcular_faltantes_priorizados(
        db,
        mes,
        anio,
        mes_stock,
        anio_stock,
        alertas,
    )
    faltantes_items: List[Dict[str, Any]] = calc["faltantes_items"]
    total_requerido = float(calc["total_requerido"])
    total_stock = float(calc["total_stock_considerado"])
    total_faltante = float(calc["total_faltante"])
    faltantes_sin_stock = int(calc["faltantes_sin_stock"])
    detalle_prioridades = calc["detalle_prioridades"]
    stock_map = cast(Dict[int, Dict[str, Any]], calc.get("stock_map") or {})

    if faltantes_sin_stock > 0:
        alertas.append(
            "Se tomó stock=0 para "
            f"{faltantes_sin_stock} componente(s) sin stock cargado en el período base {anio_stock}-{mes_stock:02d}."
        )

    capacidad_items = _calcular_capacidad_por_stock(
        db,
        mes,
        anio,
        stock_map,
        alertas,
    )

    persistencia = {"upserts": 0, "eliminados": 0}
    if persistir_sugerencias:
        try:
            persistencia = _persistir_sugerencias_compra(
                db,
                mes,
                anio,
                faltantes_items,
                alertas,
            )
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            alertas.append(
                "No se pudieron persistir sugerencias de compra. "
                f"Detalle: {exc}"
            )

    alertas_limpias = _limpiar_alertas(alertas)

    return {
        "resumen": {
            "mes": mes,
            "anio": anio,
            "mes_stock_base": mes_stock,
            "anio_stock_base": anio_stock,
            "componentes": len(faltantes_items),
            "total_requerido": total_requerido,
            "total_stock_disponible": total_stock,
            "total_faltante": total_faltante,
            "cobertura_global_pct": (
                100.0 if total_requerido <= 0 else min((total_stock / total_requerido) * 100, 100.0)
            ),
            "con_alertas": len(alertas_limpias) > 0,
        },
        "faltantes": sorted(
            faltantes_items,
            key=lambda x: (x["faltante"], x["codigo"]),
            reverse=True,
        ),
        "capacidad": capacidad_items,
        "prioridades": detalle_prioridades,
        "alertas": alertas_limpias,
        "sugerencias": {
            "persistidas": persistencia["upserts"],
            "eliminadas": persistencia["eliminados"],
            "persistir": persistir_sugerencias,
        },
    }


def calcular_asistente_oc(
    db: Session,
    mes: int,
    anio: int,
    ajustes_pt: Optional[List[Dict[str, Any]]] = None,
    persistir_sugerencias: bool = False,
) -> Dict[str, Any]:
    ajustes_pt = ajustes_pt or []
    mes_stock, anio_stock = _periodo_anterior(mes, anio)
    alertas: List[str] = []

    if not ajustes_pt:
        ajustes_pt = obtener_ajustes_pt_periodo(db, mes, anio)

    planes_base = _obtener_planes_pt_periodo(db, mes, anio)
    if not planes_base:
        return {
            "resumen": {
                "mes": mes,
                "anio": anio,
                "mes_stock_base": mes_stock,
                "anio_stock_base": anio_stock,
                "productos_pt": 0,
                "total_presuncion_original": 0.0,
                "total_stock_pt": 0.0,
                "total_deuda_clientes": 0.0,
                "total_demanda_neta_pt": 0.0,
                "componentes": 0,
                "total_faltante": 0.0,
                "cobertura_global_pct": 100.0,
                "con_alertas": False,
            },
            "demanda_neta_pt": [],
            "faltantes": [],
            "capacidad": [],
            "prioridades": [],
            "alertas": [],
            "sugerencias": {
                "persistidas": 0,
                "eliminadas": 0,
                "persistir": persistir_sugerencias,
            },
        }

    planes_por_id: Dict[int, Dict[str, Any]] = {
        int(p["producto_id"]): p for p in planes_base
    }
    codigo_a_id: Dict[str, int] = {
        str(p["codigo"]).strip().upper(): int(p["producto_id"])
        for p in planes_base
    }

    ajustes_map: Dict[int, Dict[str, float]] = {}
    for raw in ajustes_pt:
        pid = raw.get("producto_id")
        if pid is None:
            codigo_raw = str(raw.get("codigo") or "").strip().upper()
            pid = codigo_a_id.get(codigo_raw)
        if pid is None:
            continue

        pid_int = int(pid)
        if pid_int not in planes_por_id:
            continue

        stock_pt = float(raw.get("stock_pt") or 0.0)
        deuda_clientes = float(raw.get("deuda_clientes") or 0.0)
        ajustes_map[pid_int] = {
            "stock_pt": max(stock_pt, 0.0),
            "deuda_clientes": max(deuda_clientes, 0.0),
        }

    planes_ajustados: List[Dict[str, Any]] = []
    total_presuncion_original = 0.0
    total_stock_pt = 0.0
    total_deuda_clientes = 0.0
    total_demanda_neta_pt = 0.0

    for plan in planes_base:
        producto_id = int(plan["producto_id"])
        cantidad_original = float(plan.get("cantidad_planificada") or 0.0)
        ajuste = ajustes_map.get(producto_id) or {
            "stock_pt": 0.0,
            "deuda_clientes": 0.0,
        }
        stock_pt = float(ajuste.get("stock_pt") or 0.0)
        deuda_clientes = float(ajuste.get("deuda_clientes") or 0.0)
        demanda_neta = max(0.0, cantidad_original + deuda_clientes - stock_pt)

        total_presuncion_original += cantidad_original
        total_stock_pt += stock_pt
        total_deuda_clientes += deuda_clientes
        total_demanda_neta_pt += demanda_neta

        planes_ajustados.append(
            {
                "producto_id": producto_id,
                "codigo": plan["codigo"],
                "nombre": plan["nombre"],
                "cantidad_planificada": demanda_neta,
                "cantidad_original": cantidad_original,
                "stock_pt": stock_pt,
                "deuda_clientes": deuda_clientes,
                "demanda_neta": demanda_neta,
            }
        )

    planes_ajustados.sort(
        key=lambda p: (float(p.get("cantidad_planificada") or 0.0), p["codigo"]),
        reverse=True,
    )

    calc = _calcular_faltantes_priorizados_para_planes(
        db,
        planes_ajustados,
        mes_stock,
        anio_stock,
        alertas,
    )
    faltantes_items: List[Dict[str, Any]] = calc["faltantes_items"]
    total_requerido = float(calc["total_requerido"])
    total_stock = float(calc["total_stock_considerado"])
    total_faltante = float(calc["total_faltante"])
    faltantes_sin_stock = int(calc["faltantes_sin_stock"])
    detalle_prioridades = calc["detalle_prioridades"]
    stock_map = cast(Dict[int, Dict[str, Any]], calc.get("stock_map") or {})

    solicitado_laf_map = _obtener_solicitado_laf_por_producto_periodo(db, mes, anio)
    total_solicitado_laf = 0.0
    total_faltante_bruto = total_faltante

    for item in faltantes_items:
        pid = int(item.get("producto_id") or 0)
        solicitado = float(solicitado_laf_map.get(pid) or 0.0)
        faltante_bruto = float(item.get("faltante") or 0.0)
        descuento = min(faltante_bruto, solicitado)
        faltante_neto = max(0.0, faltante_bruto - descuento)

        item["solicitado_previo_laf"] = solicitado
        item["descuento_solicitado_laf"] = descuento
        item["faltante_bruto"] = faltante_bruto
        item["faltante"] = faltante_neto

        requerido = float(item.get("cantidad_requerida") or 0.0)
        stock_asignado = float(item.get("stock_asignado") or 0.0)
        if requerido > 0:
            item["cobertura_pct"] = min(((stock_asignado + descuento) / requerido) * 100, 100.0)

        total_solicitado_laf += solicitado

    total_faltante = sum(float(i.get("faltante") or 0.0) for i in faltantes_items)

    if faltantes_sin_stock > 0:
        alertas.append(
            "Se tomó stock=0 para "
            f"{faltantes_sin_stock} componente(s) sin stock cargado en el período base {anio_stock}-{mes_stock:02d}."
        )

    capacidad_items = _calcular_capacidad_por_stock_para_planes(
        db,
        planes_ajustados,
        stock_map,
        alertas,
    )

    persistencia = {"upserts": 0, "eliminados": 0}
    if persistir_sugerencias:
        try:
            persistencia = _persistir_sugerencias_compra(
                db,
                mes,
                anio,
                faltantes_items,
                alertas,
            )
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            alertas.append(
                "No se pudieron persistir sugerencias de compra. "
                f"Detalle: {exc}"
            )

    alertas_limpias = _limpiar_alertas(alertas)

    return {
        "resumen": {
            "mes": mes,
            "anio": anio,
            "mes_stock_base": mes_stock,
            "anio_stock_base": anio_stock,
            "productos_pt": len(planes_ajustados),
            "total_presuncion_original": total_presuncion_original,
            "total_stock_pt": total_stock_pt,
            "total_deuda_clientes": total_deuda_clientes,
            "total_demanda_neta_pt": total_demanda_neta_pt,
            "componentes": len(faltantes_items),
            "total_requerido": total_requerido,
            "total_stock_disponible": total_stock,
            "total_faltante_bruto": total_faltante_bruto,
            "total_solicitado_previo_laf": total_solicitado_laf,
            "total_faltante": total_faltante,
            "cobertura_global_pct": (
                100.0
                if total_requerido <= 0
                else min(
                    ((total_stock + total_solicitado_laf) / total_requerido) * 100,
                    100.0,
                )
            ),
            "con_alertas": len(alertas_limpias) > 0,
        },
        "demanda_neta_pt": sorted(
            planes_ajustados,
            key=lambda x: (x["demanda_neta"], x["codigo"]),
            reverse=True,
        ),
        "faltantes": sorted(
            faltantes_items,
            key=lambda x: (x["faltante"], x["codigo"]),
            reverse=True,
        ),
        "capacidad": capacidad_items,
        "prioridades": detalle_prioridades,
        "alertas": alertas_limpias,
        "sugerencias": {
            "persistidas": persistencia["upserts"],
            "eliminadas": persistencia["eliminados"],
            "persistir": persistir_sugerencias,
        },
    }


def guardar_bulk(db: Session, mes: int, anio: int, items: List[dict]) -> int:
    """Upsert en lote de cantidades para un mes/año."""
    total_upserts = 0
    for item in items:
        pid = int(item["producto_id"])
        cant = float(item.get("cantidad", 0))
        existe = db.execute(
            text(
                "SELECT id FROM plan_produccion_mensual "
                "WHERE producto_id=:pid AND mes=:mes AND anio=:anio"
            ),
            {"pid": pid, "mes": mes, "anio": anio},
        ).first()
        if existe:
            db.execute(
                text(
                    "UPDATE plan_produccion_mensual "
                    "SET cantidad_planificada=:cantidad WHERE id=:id"
                ),
                {"cantidad": cant, "id": existe.id},
            )
        else:
            db.execute(
                text(
                    "INSERT INTO plan_produccion_mensual (producto_id, mes, anio, "
                    "cantidad_planificada) VALUES (:pid, :mes, :anio, :cant)"
                ),
                {"pid": pid, "mes": mes, "anio": anio, "cant": cant},
            )
        total_upserts += 1
    db.commit()
    return total_upserts


def mapear_codigo_a_id(db: Session) -> dict:
    rows = db.execute(
        text(
            "SELECT id, codigo FROM producto "
            "WHERE tipo_producto='PT' AND activo=1"
        )
    ).fetchall()
    return {row.codigo.strip(): int(row.id) for row in rows}


def importar_desde_rows(
    db: Session,
    rows: List[dict],
    mes_override: int | None = None,
    anio_override: int | None = None,
) -> int:
    """Importa filas con claves codigo, mes, anio, cantidad.

    Si `mes_override` y `anio_override` se informan, se usan para todas las filas.
    """
    codigo_map = mapear_codigo_a_id(db)
    procesadas = 0
    for row in rows:
        codigo = str(row.get("codigo", "")).strip()
        if not codigo:
            continue
        pid = codigo_map.get(codigo)
        if not pid:
            continue
        try:
            if mes_override is not None and anio_override is not None:
                mes = int(mes_override)
                anio = int(anio_override)
            else:
                mes_raw = row.get("mes")
                anio_raw = row.get("anio")
                if mes_raw is None or anio_raw is None:
                    continue
                mes = int(mes_raw)
                anio = int(anio_raw)
            cantidad = float(row.get("cantidad", 0))
        except (TypeError, ValueError):
            continue
        guardar_bulk(db, mes, anio, [{"producto_id": pid, "cantidad": cantidad}])
        procesadas += 1
    return procesadas
