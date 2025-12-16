from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Tuple
from app.models.plan_produccion import PlanProduccionCreate, PlanProduccionUpdate

def listar_planes(db: Session, limit: int = 20, offset: int = 0, mes: Optional[int] = None, anio: Optional[int] = None, producto_id: Optional[int] = None) -> Tuple[List[dict], int]:
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
        SELECT p.id, p.producto_id, pr.codigo as producto_codigo, pr.nombre as producto_nombre, p.mes, p.anio, p.cantidad
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
    # Validar duplicado
    existe = db.execute(text("SELECT 1 FROM plan_produccion_mensual WHERE producto_id=:pid AND mes=:mes AND anio=:anio"), {"pid": plan.producto_id, "mes": plan.mes, "anio": plan.anio}).first()
    if existe:
        raise ValueError("Ya existe un plan para ese producto, mes y año")
    res = db.execute(text("""
        INSERT INTO plan_produccion_mensual (producto_id, mes, anio, cantidad)
        VALUES (:pid, :mes, :anio, :cantidad)
    """), {"pid": plan.producto_id, "mes": plan.mes, "anio": plan.anio, "cantidad": plan.cantidad})
    db.commit()
    return res.lastrowid

def actualizar_plan(db: Session, plan_id: int, plan: PlanProduccionUpdate):
    existe = db.execute(text("SELECT id FROM plan_produccion_mensual WHERE producto_id=:pid AND mes=:mes AND anio=:anio AND id != :id"), {"pid": plan.producto_id, "mes": plan.mes, "anio": plan.anio, "id": plan_id}).first()
    if existe:
        raise ValueError("Ya existe un plan para ese producto, mes y año")
    db.execute(text("""
        UPDATE plan_produccion_mensual SET producto_id=:pid, mes=:mes, anio=:anio, cantidad=:cantidad WHERE id=:id
    """), {"pid": plan.producto_id, "mes": plan.mes, "anio": plan.anio, "cantidad": plan.cantidad, "id": plan_id})
    db.commit()

def eliminar_plan(db: Session, plan_id: int):
    db.execute(text("DELETE FROM plan_produccion_mensual WHERE id=:id"), {"id": plan_id})
    db.commit()
