"""
Servicio para gestión de operaciones (catálogo maestro).
"""
from typing import Optional
from sqlalchemy import text
from sqlalchemy.orm import Session


def listar_operaciones(
    db: Session,
    q: Optional[str] = None,
    centro_trabajo: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Lista operaciones con filtros opcionales."""
    where_clauses = []
    params = {"limit": limit, "offset": offset}

    if q:
        where_clauses.append(
            "(o.codigo LIKE :q OR o.nombre LIKE :q OR o.centro_trabajo LIKE :q)"
        )
        params["q"] = f"%{q}%"

    if centro_trabajo:
        where_clauses.append("o.centro_trabajo = :centro")
        params["centro"] = centro_trabajo

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    query = text(f"""
        SELECT 
            o.id,
            o.codigo,
            o.nombre,
            o.centro_trabajo,
            o.tiempo_estandar_minutos,
            o.costo_hora,
            o.moneda,
            o.fecha_creacion,
            o.fecha_actualizacion
        FROM operacion o
        WHERE {where_sql}
        ORDER BY o.codigo
        LIMIT :limit OFFSET :offset
    """)

    rows = db.execute(query, params).fetchall()
    return [
        {
            "id": r.id,
            "codigo": r.codigo,
            "nombre": r.nombre,
            "centro_trabajo": r.centro_trabajo,
            "tiempo_estandar_minutos": float(r.tiempo_estandar_minutos or 0),
            "costo_hora": float(r.costo_hora or 0),
            "moneda": r.moneda,
            "fecha_creacion": r.fecha_creacion.isoformat() if r.fecha_creacion else None,
            "fecha_actualizacion": r.fecha_actualizacion.isoformat() if r.fecha_actualizacion else None,
        }
        for r in rows
    ]


def obtener_operacion(db: Session, operacion_id: int) -> Optional[dict]:
    """Obtiene una operación por ID."""
    query = text("""
        SELECT 
            o.id,
            o.codigo,
            o.nombre,
            o.centro_trabajo,
            o.tiempo_estandar_minutos,
            o.costo_hora,
            o.moneda,
            o.fecha_creacion,
            o.fecha_actualizacion
        FROM operacion o
        WHERE o.id = :id
    """)
    
    row = db.execute(query, {"id": operacion_id}).fetchone()
    if not row:
        return None
    
    return {
        "id": row.id,
        "codigo": row.codigo,
        "nombre": row.nombre,
        "centro_trabajo": row.centro_trabajo,
        "tiempo_estandar_minutos": float(row.tiempo_estandar_minutos or 0),
        "costo_hora": float(row.costo_hora or 0),
        "moneda": row.moneda,
        "fecha_creacion": row.fecha_creacion.isoformat() if row.fecha_creacion else None,
        "fecha_actualizacion": row.fecha_actualizacion.isoformat() if row.fecha_actualizacion else None,
    }


def crear_operacion(
    db: Session,
    codigo: str,
    nombre: str,
    centro_trabajo: str,
    tiempo_estandar_minutos: float = 0,
    costo_hora: float = 0,
    moneda: str = "ARS",
) -> dict:
    """Crea una nueva operación."""
    query = text("""
        INSERT INTO operacion 
        (codigo, nombre, centro_trabajo, tiempo_estandar_minutos, costo_hora, moneda)
        VALUES 
        (:codigo, :nombre, :centro, :tiempo, :costo, :moneda)
    """)
    
    result = db.execute(query, {
        "codigo": codigo,
        "nombre": nombre,
        "centro": centro_trabajo,
        "tiempo": tiempo_estandar_minutos,
        "costo": costo_hora,
        "moneda": moneda,
    })
    db.commit()
    
    return obtener_operacion(db, result.lastrowid)


def actualizar_operacion(
    db: Session,
    operacion_id: int,
    codigo: Optional[str] = None,
    nombre: Optional[str] = None,
    centro_trabajo: Optional[str] = None,
    tiempo_estandar_minutos: Optional[float] = None,
    costo_hora: Optional[float] = None,
    moneda: Optional[str] = None,
) -> Optional[dict]:
    """Actualiza una operación existente."""
    updates = []
    params = {"id": operacion_id}
    
    if codigo is not None:
        updates.append("codigo = :codigo")
        params["codigo"] = codigo
    
    if nombre is not None:
        updates.append("nombre = :nombre")
        params["nombre"] = nombre
    
    if centro_trabajo is not None:
        updates.append("centro_trabajo = :centro")
        params["centro"] = centro_trabajo
    
    if tiempo_estandar_minutos is not None:
        updates.append("tiempo_estandar_minutos = :tiempo")
        params["tiempo"] = tiempo_estandar_minutos
    
    if costo_hora is not None:
        updates.append("costo_hora = :costo")
        params["costo"] = costo_hora
    
    if moneda is not None:
        updates.append("moneda = :moneda")
        params["moneda"] = moneda
    
    if not updates:
        return obtener_operacion(db, operacion_id)
    
    updates.append("fecha_actualizacion = CURRENT_TIMESTAMP")
    update_sql = ", ".join(updates)
    
    query = text(f"""
        UPDATE operacion 
        SET {update_sql}
        WHERE id = :id
    """)
    
    db.execute(query, params)
    db.commit()
    
    return obtener_operacion(db, operacion_id)


def eliminar_operacion(db: Session, operacion_id: int) -> bool:
    """Elimina una operación (solo si no está referenciada)."""
    query = text("DELETE FROM operacion WHERE id = :id")
    result = db.execute(query, {"id": operacion_id})
    db.commit()
    return result.rowcount > 0
