"""
Servicio para gestión de la ruta de operaciones de un MBOM (mbom_operacion).
"""
from typing import Optional
from sqlalchemy import text
from sqlalchemy.orm import Session


def listar_operaciones_mbom(db: Session, mbom_id: int) -> list[dict]:
    """Lista las operaciones de un MBOM en orden de secuencia."""
    query = text("""
        SELECT 
            mo.id,
            mo.mbom_id,
            mo.secuencia,
            mo.operacion_id,
            mo.notas,
            o.codigo AS operacion_codigo,
            o.nombre AS operacion_nombre,
            o.centro_trabajo,
            o.tiempo_estandar_minutos,
            o.costo_hora,
            o.moneda
        FROM mbom_operacion mo
        INNER JOIN operacion o ON mo.operacion_id = o.id
        WHERE mo.mbom_id = :mbom_id
        ORDER BY mo.secuencia
    """)
    
    rows = db.execute(query, {"mbom_id": mbom_id}).fetchall()
    return [
        {
            "id": r.id,
            "mbom_id": r.mbom_id,
            "secuencia": r.secuencia,
            "operacion_id": r.operacion_id,
            "operacion_codigo": r.operacion_codigo,
            "operacion_nombre": r.operacion_nombre,
            "centro_trabajo": r.centro_trabajo,
            "tiempo_estandar_minutos": float(r.tiempo_estandar_minutos or 0),
            "costo_hora": float(r.costo_hora or 0),
            "moneda": r.moneda,
            "notas": r.notas,
        }
        for r in rows
    ]


def agregar_operacion_mbom(
    db: Session,
    mbom_id: int,
    operacion_id: int,
    secuencia: int,
    notas: Optional[str] = None,
) -> dict:
    """Agrega una operación a la ruta del MBOM."""
    query = text("""
        INSERT INTO mbom_operacion 
        (mbom_id, operacion_id, secuencia, notas)
        VALUES 
        (:mbom_id, :operacion_id, :secuencia, :notas)
    """)
    
    result = db.execute(query, {
        "mbom_id": mbom_id,
        "operacion_id": operacion_id,
        "secuencia": secuencia,
        "notas": notas,
    })
    db.commit()
    
    # Retornar la operación completa
    ops = listar_operaciones_mbom(db, mbom_id)
    for op in ops:
        if op["id"] == result.lastrowid:
            return op
    
    return {"id": result.lastrowid, "mbom_id": mbom_id, "secuencia": secuencia}


def actualizar_operacion_mbom(
    db: Session,
    mbom_operacion_id: int,
    secuencia: Optional[int] = None,
    notas: Optional[str] = None,
) -> bool:
    """Actualiza una operación en la ruta del MBOM."""
    updates = []
    params = {"id": mbom_operacion_id}
    
    if secuencia is not None:
        updates.append("secuencia = :secuencia")
        params["secuencia"] = secuencia
    
    if notas is not None:
        updates.append("notas = :notas")
        params["notas"] = notas
    
    if not updates:
        return True
    
    update_sql = ", ".join(updates)
    query = text(f"""
        UPDATE mbom_operacion 
        SET {update_sql}
        WHERE id = :id
    """)
    
    db.execute(query, params)
    db.commit()
    return True


def eliminar_operacion_mbom(db: Session, mbom_operacion_id: int) -> bool:
    """Elimina una operación de la ruta del MBOM."""
    query = text("DELETE FROM mbom_operacion WHERE id = :id")
    result = db.execute(query, {"id": mbom_operacion_id})
    db.commit()
    return result.rowcount > 0


def obtener_siguiente_secuencia(db: Session, mbom_id: int) -> int:
    """Obtiene la siguiente secuencia disponible (múltiplo de 10)."""
    query = text("""
        SELECT COALESCE(MAX(secuencia), 0) + 10 AS next_seq
        FROM mbom_operacion
        WHERE mbom_id = :mbom_id
    """)
    
    row = db.execute(query, {"mbom_id": mbom_id}).fetchone()
    return row.next_seq if row else 10
