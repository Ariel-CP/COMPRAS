from typing import List
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..schemas.plan import PlanItemIn, PlanItemOut, PlanUpsertResult


def _get_producto_id(db: Session, codigo: str) -> int | None:
    q = text("SELECT id FROM producto WHERE codigo = :codigo AND activo = 1")
    res = db.execute(q, {"codigo": codigo}).first()
    return int(res[0]) if res else None


def get_plan_periodo(db: Session, anio: int, mes: int) -> List[PlanItemOut]:
    q = text(
        """
        SELECT ppm.id, ppm.anio, ppm.mes, p.codigo AS producto_codigo, ppm.cantidad_planificada
        FROM plan_produccion_mensual ppm
        JOIN producto p ON p.id = ppm.producto_id
        WHERE ppm.anio = :anio AND ppm.mes = :mes
        ORDER BY p.codigo
        """
    )
    rows = db.execute(q, {"anio": anio, "mes": mes}).mappings().all()
    return [
        PlanItemOut(
            id=row["id"],
            anio=row["anio"],
            mes=row["mes"],
            producto_codigo=row["producto_codigo"],
            cantidad_planificada=row["cantidad_planificada"],
        )
        for row in rows
    ]


def upsert_plan_periodo(
    db: Session, anio: int, mes: int, items: List[PlanItemIn], sobrescribir: bool
) -> PlanUpsertResult:
    insertados = 0
    actualizados = 0
    rechazados = 0
    errores: List[str] = []

    if sobrescribir:
        db.execute(text("DELETE FROM plan_produccion_mensual WHERE anio=:a AND mes=:m"), {"a": anio, "m": mes})

    for it in items:
        prod_id = _get_producto_id(db, it.producto_codigo)
        if not prod_id:
            rechazados += 1
            errores.append(f"Producto no encontrado: {it.producto_codigo}")
            continue

        if sobrescribir:
            ins = text(
                """
                INSERT INTO plan_produccion_mensual (anio, mes, producto_id, cantidad_planificada)
                VALUES (:anio, :mes, :pid, :cant)
                """
            )
            db.execute(ins, {"anio": anio, "mes": mes, "pid": prod_id, "cant": it.cantidad})
            insertados += 1
        else:
            upd = text(
                """
                UPDATE plan_produccion_mensual
                SET cantidad_planificada = :cant
                WHERE anio=:anio AND mes=:mes AND producto_id=:pid
                """
            )
            r = db.execute(
                upd,
                {"cant": it.cantidad, "anio": anio, "mes": mes, "pid": prod_id},
            )
            if r.rowcount and r.rowcount > 0:
                actualizados += 1
            else:
                ins = text(
                    """
                    INSERT INTO plan_produccion_mensual (anio, mes, producto_id, cantidad_planificada)
                    VALUES (:anio, :mes, :pid, :cant)
                    """
                )
                db.execute(ins, {"anio": anio, "mes": mes, "pid": prod_id, "cant": it.cantidad})
                insertados += 1

    return PlanUpsertResult(
        insertados=insertados, actualizados=actualizados, rechazados=rechazados, errores=errores
    )


def update_plan_item(db: Session, item_id: int, body: PlanItemIn) -> PlanItemOut:
    # Actualiza cantidad por id; luego devuelve el registro con codigo
    upd = text(
        "UPDATE plan_produccion_mensual SET cantidad_planificada=:cant WHERE id=:id"
    )
    r = db.execute(upd, {"cant": body.cantidad, "id": item_id})
    if r.rowcount == 0:
        raise ValueError("Item no encontrado")

    q = text(
        """
        SELECT ppm.id, ppm.anio, ppm.mes, p.codigo AS producto_codigo, ppm.cantidad_planificada
        FROM plan_produccion_mensual ppm
        JOIN producto p ON p.id = ppm.producto_id
        WHERE ppm.id = :id
        """
    )
    row = db.execute(q, {"id": item_id}).mappings().first()
    if not row:
        raise ValueError("Item no encontrado")

    return PlanItemOut(
        id=row["id"],
        anio=row["anio"],
        mes=row["mes"],
        producto_codigo=row["producto_codigo"],
        cantidad_planificada=row["cantidad_planificada"],
    )


def delete_plan_periodo(db: Session, anio: int, mes: int) -> None:
    db.execute(text("DELETE FROM plan_produccion_mensual WHERE anio=:a AND mes=:m"), {"a": anio, "m": mes})
