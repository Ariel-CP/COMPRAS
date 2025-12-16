from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Tuple
from app.models.plan_produccion import PlanProduccionCreate, PlanProduccionUpdate


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
        SELECT p.id, p.producto_id, pr.codigo as producto_codigo, pr.nombre as producto_nombre, p.mes, p.anio, p.cantidad_planificada AS cantidad
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
    total = db.execute(text(count_sql), params).scalar()
    return [dict(row) for row in rows], total


def crear_plan(db: Session, plan: PlanProduccionCreate) -> int:
    existe = db.execute(
        text(
            "SELECT 1 FROM plan_produccion_mensual WHERE producto_id=:pid AND mes=:mes AND anio=:anio"
        ),
        {"pid": plan.producto_id, "mes": plan.mes, "anio": plan.anio},
    ).first()
    if existe:
        raise ValueError("Ya existe un plan para ese producto, mes y año")
    res = db.execute(
        text(
            """
        INSERT INTO plan_produccion_mensual (producto_id, mes, anio, cantidad_planificada)
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
    return res.lastrowid


def actualizar_plan(db: Session, plan_id: int, plan: PlanProduccionUpdate):
    existe = db.execute(
        text(
            "SELECT id FROM plan_produccion_mensual WHERE producto_id=:pid AND mes=:mes AND anio=:anio AND id != :id"
        ),
        {"pid": plan.producto_id, "mes": plan.mes, "anio": plan.anio, "id": plan_id},
    ).first()
    if existe:
        raise ValueError("Ya existe un plan para ese producto, mes y año")
    db.execute(
        text(
            """
        UPDATE plan_produccion_mensual SET producto_id=:pid, mes=:mes, anio=:anio, cantidad_planificada=:cantidad WHERE id=:id
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
    db.execute(text("DELETE FROM plan_produccion_mensual WHERE id=:id"), {"id": plan_id})
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


def guardar_bulk(db: Session, mes: int, anio: int, items: List[dict]) -> int:
    """Upsert en lote de cantidades para un mes/año."""
    total_upserts = 0
    for item in items:
        pid = int(item["producto_id"])
        cant = float(item.get("cantidad", 0))
        existe = db.execute(
            text(
                "SELECT id FROM plan_produccion_mensual WHERE producto_id=:pid AND mes=:mes AND anio=:anio"
            ),
            {"pid": pid, "mes": mes, "anio": anio},
        ).first()
        if existe:
            db.execute(
                text(
                    "UPDATE plan_produccion_mensual SET cantidad_planificada=:cantidad WHERE id=:id"
                ),
                {"cantidad": cant, "id": existe.id},
            )
        else:
            db.execute(
                text(
                    "INSERT INTO plan_produccion_mensual (producto_id, mes, anio, cantidad_planificada) VALUES (:pid, :mes, :anio, :cant)"
                ),
                {"pid": pid, "mes": mes, "anio": anio, "cant": cant},
            )
        total_upserts += 1
    db.commit()
    return total_upserts


def mapear_codigo_a_id(db: Session) -> dict:
    rows = db.execute(text("SELECT id, codigo FROM producto WHERE tipo_producto='PT' AND activo=1")).fetchall()
    return {row.codigo.strip(): int(row.id) for row in rows}


def importar_desde_rows(db: Session, rows: List[dict]) -> int:
    """Importa filas con claves codigo, mes, anio, cantidad. Devuelve cantidad procesada."""
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
            mes = int(row.get("mes"))
            anio = int(row.get("anio"))
            cantidad = float(row.get("cantidad", 0))
        except (TypeError, ValueError):
            continue
        guardar_bulk(db, mes, anio, [{"producto_id": pid, "cantidad": cantidad}])
        procesadas += 1
    return procesadas
