"""Servicios para plantillas de ruta de operaciones reutilizables."""
from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from . import mbom_operacion_service


def listar_rutas_base(
    db: Session,
    q: Optional[str] = None,
    solo_activas: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    where = ["1=1"]
    params: dict[str, object] = {"limit": limit, "offset": offset}
    if q:
        where.append("(r.nombre LIKE :q OR r.descripcion LIKE :q)")
        params["q"] = f"%{q}%"
    if solo_activas is not None:
        where.append("r.esta_activo = :activo")
        params["activo"] = 1 if solo_activas else 0

    query = text(
        f"""
        SELECT
            r.id,
            r.nombre,
            r.descripcion,
            r.esta_activo,
            r.creado_por,
            r.actualizado_por,
            r.fecha_creacion,
            r.fecha_actualizacion,
            (
                SELECT COUNT(*)
                FROM ruta_operacion_base_detalle d
                WHERE d.ruta_id = r.id
            ) AS total_operaciones
        FROM ruta_operacion_base r
        WHERE {' AND '.join(where)}
        ORDER BY r.nombre
        LIMIT :limit OFFSET :offset
        """
    )
    rows = db.execute(query, params).fetchall()
    return [
        {
            "id": row.id,
            "nombre": row.nombre,
            "descripcion": row.descripcion,
            "esta_activo": bool(row.esta_activo),
            "creado_por": row.creado_por,
            "actualizado_por": row.actualizado_por,
            "fecha_creacion": row.fecha_creacion.isoformat()
            if row.fecha_creacion
            else None,
            "fecha_actualizacion": row.fecha_actualizacion.isoformat()
            if row.fecha_actualizacion
            else None,
            "total_operaciones": row.total_operaciones,
        }
        for row in rows
    ]


def obtener_ruta_base(db: Session, ruta_id: int) -> Optional[dict]:
    ruta_query = text(
        """
        SELECT
            r.id,
            r.nombre,
            r.descripcion,
            r.esta_activo,
            r.creado_por,
            r.actualizado_por,
            r.fecha_creacion,
            r.fecha_actualizacion
        FROM ruta_operacion_base r
        WHERE r.id = :id
        """
    )
    ruta_row = db.execute(ruta_query, {"id": ruta_id}).fetchone()
    if not ruta_row:
        return None

    detalles = listar_detalles_ruta(db, ruta_id)
    return {
        "id": ruta_row.id,
        "nombre": ruta_row.nombre,
        "descripcion": ruta_row.descripcion,
        "esta_activo": bool(ruta_row.esta_activo),
        "creado_por": ruta_row.creado_por,
        "actualizado_por": ruta_row.actualizado_por,
        "fecha_creacion": ruta_row.fecha_creacion.isoformat()
        if ruta_row.fecha_creacion
        else None,
        "fecha_actualizacion": ruta_row.fecha_actualizacion.isoformat()
        if ruta_row.fecha_actualizacion
        else None,
        "detalles": detalles,
    }


def listar_detalles_ruta(db: Session, ruta_id: int) -> list[dict]:
    detalle_query = text(
        """
        SELECT
            d.id,
            d.ruta_id,
            d.secuencia,
            d.operacion_id,
            d.notas,
            o.codigo AS operacion_codigo,
            o.nombre AS operacion_nombre,
            o.centro_trabajo,
            o.tiempo_estandar_minutos,
            o.costo_hora,
            o.moneda
        FROM ruta_operacion_base_detalle d
        INNER JOIN operacion o ON o.id = d.operacion_id
        WHERE d.ruta_id = :ruta_id
        ORDER BY d.secuencia
        """
    )
    rows = db.execute(detalle_query, {"ruta_id": ruta_id}).fetchall()
    return [
        {
            "id": row.id,
            "ruta_id": row.ruta_id,
            "secuencia": row.secuencia,
            "operacion_id": row.operacion_id,
            "operacion_codigo": row.operacion_codigo,
            "operacion_nombre": row.operacion_nombre,
            "centro_trabajo": row.centro_trabajo,
            "tiempo_estandar_minutos": float(row.tiempo_estandar_minutos or 0),
            "costo_hora": float(row.costo_hora or 0),
            "moneda": row.moneda,
            "notas": row.notas,
        }
        for row in rows
    ]


def crear_ruta_base(
    db: Session,
    nombre: str,
    descripcion: Optional[str],
    detalles: Iterable[dict],
    esta_activo: bool = True,
    creado_por: Optional[str] = None,
) -> dict:
    detalles_list = sorted(
        (
            {
                "operacion_id": int(det["operacion_id"]),
                "secuencia": int(det.get("secuencia", 0) or 0),
                "notas": det.get("notas"),
            }
            for det in detalles
        ),
        key=lambda item: item["secuencia"],
    )
    if not detalles_list:
        raise ValueError("La ruta debe incluir al menos una operación")

    for det in detalles_list:
        if det["secuencia"] <= 0:
            raise ValueError("Las secuencias deben ser positivas")

    insert_ruta = text(
        """
        INSERT INTO ruta_operacion_base
            (nombre, descripcion, esta_activo, creado_por, actualizado_por)
        VALUES
            (:nombre, :descripcion, :activo, :creado_por, :actualizado_por)
        """
    )
    result = db.execute(
        insert_ruta,
        {
            "nombre": nombre,
            "descripcion": descripcion,
            "activo": 1 if esta_activo else 0,
            "creado_por": creado_por,
            "actualizado_por": creado_por,
        },
    )
    ruta_id = int(result.lastrowid)

    insert_detalle = text(
        """
        INSERT INTO ruta_operacion_base_detalle
            (ruta_id, secuencia, operacion_id, notas)
        VALUES
            (:ruta_id, :secuencia, :operacion_id, :notas)
        """
    )
    for det in detalles_list:
        db.execute(
            insert_detalle,
            {
                "ruta_id": ruta_id,
                "secuencia": det["secuencia"],
                "operacion_id": det["operacion_id"],
                "notas": det.get("notas"),
            },
        )

    db.commit()
    return obtener_ruta_base(db, ruta_id)  # type: ignore[return-value]


def actualizar_ruta_base(
    db: Session,
    ruta_id: int,
    nombre: Optional[str] = None,
    descripcion: Optional[str] = None,
    esta_activo: Optional[bool] = None,
    actualizado_por: Optional[str] = None,
    detalles: Optional[Iterable[dict]] = None,
) -> dict:
    updates: list[str] = []
    params: dict[str, object] = {"id": ruta_id}

    if nombre is not None:
        updates.append("nombre = :nombre")
        params["nombre"] = nombre
    if descripcion is not None:
        updates.append("descripcion = :descripcion")
        params["descripcion"] = descripcion
    if esta_activo is not None:
        updates.append("esta_activo = :activo")
        params["activo"] = 1 if esta_activo else 0
    if actualizado_por is not None:
        updates.append("actualizado_por = :actualizado_por")
        params["actualizado_por"] = actualizado_por

    if updates:
        updates.append("fecha_actualizacion = CURRENT_TIMESTAMP")
        update_sql = ", ".join(updates)
        db.execute(
            text(
                f"""
                UPDATE ruta_operacion_base
                SET {update_sql}
                WHERE id = :id
                """
            ),
            params,
        )

    if detalles is not None:
        detalles_list = sorted(
            (
                {
                    "secuencia": int(det.get("secuencia", 0) or 0),
                    "operacion_id": int(det["operacion_id"]),
                    "notas": det.get("notas"),
                }
                for det in detalles
            ),
            key=lambda item: item["secuencia"],
        )
        for det in detalles_list:
            if det["secuencia"] <= 0:
                raise ValueError("Las secuencias deben ser positivas")
        db.execute(
            text(
                "DELETE FROM ruta_operacion_base_detalle WHERE ruta_id = :ruta_id"
            ),
            {"ruta_id": ruta_id},
        )
        insert_detalle = text(
            """
            INSERT INTO ruta_operacion_base_detalle
                (ruta_id, secuencia, operacion_id, notas)
            VALUES
                (:ruta_id, :secuencia, :operacion_id, :notas)
            """
        )
        for det in detalles_list:
            db.execute(
                insert_detalle,
                {
                    "ruta_id": ruta_id,
                    "secuencia": det["secuencia"],
                    "operacion_id": det["operacion_id"],
                    "notas": det.get("notas"),
                },
            )

    db.commit()
    ruta = obtener_ruta_base(db, ruta_id)
    if not ruta:
        raise ValueError("Ruta no encontrada después de actualizar")
    return ruta


def eliminar_ruta_base(db: Session, ruta_id: int) -> bool:
    result = db.execute(
        text("DELETE FROM ruta_operacion_base WHERE id = :id"),
        {"id": ruta_id},
    )
    db.commit()
    return bool(result.rowcount)  # type: ignore[attr-defined]


def crear_ruta_base_desde_mbom(
    db: Session,
    mbom_id: int,
    nombre: str,
    descripcion: Optional[str] = None,
    esta_activo: bool = True,
    creado_por: Optional[str] = None,
) -> dict:
    operaciones = mbom_operacion_service.listar_operaciones_mbom(db, mbom_id)
    if not operaciones:
        raise ValueError("El MBOM no tiene operaciones para copiar")

    detalles = (
        {
            "operacion_id": op["operacion_id"],
            "secuencia": op["secuencia"],
            "notas": op.get("notas"),
        }
        for op in operaciones
    )
    return crear_ruta_base(
        db,
        nombre=nombre,
        descripcion=descripcion,
        detalles=detalles,
        esta_activo=esta_activo,
        creado_por=creado_por,
    )


def aplicar_ruta_base_a_mbom(
    db: Session,
    ruta_id: int,
    mbom_id: int,
    reemplazar: bool = False,
    mantener_secuencia: bool = False,
) -> list[dict]:
    ruta = obtener_ruta_base(db, ruta_id)
    if not ruta:
        raise ValueError("Ruta de operaciones no encontrada")

    detalles = ruta.get("detalles", []) or []
    if not detalles:
        raise ValueError("La ruta seleccionada no tiene operaciones asignadas")

    if reemplazar:
        db.execute(
            text("DELETE FROM mbom_operacion WHERE mbom_id = :mbom_id"),
            {"mbom_id": mbom_id},
        )
        secuencias_existentes: set[int] = set()
        siguiente_secuencia = 10
    else:
        existentes_rows = db.execute(
            text(
                "SELECT secuencia FROM mbom_operacion "
                "WHERE mbom_id = :mbom_id ORDER BY secuencia"
            ),
            {"mbom_id": mbom_id},
        ).fetchall()
        secuencias_existentes = {row.secuencia for row in existentes_rows}
        max_seq = max(secuencias_existentes) if secuencias_existentes else 0
        siguiente_secuencia = ((max_seq // 10) * 10) + 10 if max_seq else 10

    insert_sql = text(
        """
        INSERT INTO mbom_operacion (mbom_id, operacion_id, secuencia, notas)
        VALUES (:mbom_id, :operacion_id, :secuencia, :notas)
        """
    )

    for det in detalles:
        if mantener_secuencia:
            secuencia = int(det["secuencia"])
            while secuencia in secuencias_existentes:
                secuencia += 10
        else:
            secuencia = siguiente_secuencia
            siguiente_secuencia += 10
        secuencias_existentes.add(secuencia)
        db.execute(
            insert_sql,
            {
                "mbom_id": mbom_id,
                "operacion_id": int(det["operacion_id"]),
                "secuencia": secuencia,
                "notas": det.get("notas"),
            },
        )

    db.commit()
    return mbom_operacion_service.listar_operaciones_mbom(db, mbom_id)
