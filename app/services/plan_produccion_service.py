from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

import app.services.mbom_costos as mbom_costos
import app.services.mbom_service as mbom_service
from app.models.plan_produccion import (
    PlanProduccionCreate,
    PlanProduccionUpdate,
)


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
            ORDER BY p.nombre
            """
        ),
        {"mes": mes, "anio": anio},
    ).fetchall()

    capacidad_items: List[Dict[str, Any]] = []
    for row in planes:
        producto_id = int(row.producto_id)
        mbom = mbom_service.get_cabecera_preferida(db, producto_id, "ACTIVO")
        if not mbom:
            alertas.append(
                "No hay MBOM activa vigente para "
                f"{row.codigo}; no se puede calcular capacidad."
            )
            capacidad_items.append(
                {
                    "producto_id": producto_id,
                    "codigo": row.codigo,
                    "nombre": row.nombre,
                    "cantidad_planificada": float(row.cantidad_planificada or 0),
                    "max_fabricable": 0.0,
                    "max_fabricable_entero": 0,
                    "faltante_pt": float(row.cantidad_planificada or 0),
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
                f"{row.codigo} no tiene componentes hoja para calcular capacidad."
            )
            capacidad_items.append(
                {
                    "producto_id": producto_id,
                    "codigo": row.codigo,
                    "nombre": row.nombre,
                    "cantidad_planificada": float(row.cantidad_planificada or 0),
                    "max_fabricable": 0.0,
                    "max_fabricable_entero": 0,
                    "faltante_pt": float(row.cantidad_planificada or 0),
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
        planificado = float(row.cantidad_planificada or 0.0)
        faltante_pt = max(0.0, planificado - max_fabricable_entero)
        cobertura = 0.0 if planificado <= 0 else (max_fabricable_entero / planificado) * 100

        capacidad_items.append(
            {
                "producto_id": producto_id,
                "codigo": row.codigo,
                "nombre": row.nombre,
                "cantidad_planificada": planificado,
                "max_fabricable": max_fabricable_val,
                "max_fabricable_entero": max_fabricable_entero,
                "faltante_pt": faltante_pt,
                "cobertura_plan_pct": min(cobertura, 100.0),
                "componente_limitante": limitante,
            }
        )

    return capacidad_items


def calcular_faltantes_y_capacidad(
    db: Session,
    mes: int,
    anio: int,
    persistir_sugerencias: bool = True,
) -> Dict[str, Any]:
    requerimientos = calcular_requerimientos_valorizados(
        db,
        mes,
        anio,
        persistir=persistir_sugerencias,
    )
    stock_map = _obtener_stock_periodo(db, mes, anio)
    alertas: List[str] = []

    faltantes_items: List[Dict[str, Any]] = []
    total_requerido = 0.0
    total_stock = 0.0
    total_faltante = 0.0

    faltantes_sin_stock = 0
    for item in requerimientos.get("items", []):
        producto_id = int(item["producto_id"])
        cantidad_requerida = float(item.get("cantidad") or 0.0)
        stock_info = stock_map.get(producto_id)
        stock_disponible = (
            float(stock_info.get("stock_disponible") or 0.0)
            if stock_info
            else 0.0
        )

        if stock_info is None and cantidad_requerida > 0:
            faltantes_sin_stock += 1

        faltante = max(0.0, cantidad_requerida - stock_disponible)
        cobertura = 100.0
        if cantidad_requerida > 0:
            cobertura = min((stock_disponible / cantidad_requerida) * 100, 100.0)

        faltantes_items.append(
            {
                "producto_id": producto_id,
                "codigo": item["codigo"],
                "nombre": item["nombre"],
                "unidad_medida_id": int(item["unidad_medida_id"]),
                "um_codigo": item["um_codigo"],
                "cantidad_requerida": cantidad_requerida,
                "stock_disponible": stock_disponible,
                "faltante": faltante,
                "cobertura_pct": cobertura,
                "fecha_corte_stock": (
                    stock_info.get("fecha_corte") if stock_info else None
                ),
                "origen_stock": stock_info.get("origen") if stock_info else None,
            }
        )

        total_requerido += cantidad_requerida
        total_stock += stock_disponible
        total_faltante += faltante

        if bool(item.get("activo", True)) is False:
            alertas.append(
                f"El componente {item['codigo']} está inactivo y participa en la estructura."
            )

    if faltantes_sin_stock > 0:
        alertas.append(
            "Se tomó stock=0 para "
            f"{faltantes_sin_stock} componente(s) sin stock cargado en el período."
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
        persistencia = _persistir_sugerencias_compra(
            db,
            mes,
            anio,
            faltantes_items,
            alertas,
        )
        db.commit()

    # Remover alertas duplicadas y vacías manteniendo orden.
    alertas_limpias: List[str] = []
    seen = set()
    for alerta in alertas:
        alerta_txt = str(alerta or "").strip()
        if not alerta_txt or alerta_txt in seen:
            continue
        seen.add(alerta_txt)
        alertas_limpias.append(alerta_txt)

    return {
        "resumen": {
            "mes": mes,
            "anio": anio,
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


def importar_desde_rows(db: Session, rows: List[dict]) -> int:
    """Importa filas con claves codigo, mes, anio, cantidad."""
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
