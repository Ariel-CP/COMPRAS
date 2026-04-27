from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


def _to_bool_sql(value: bool) -> int:
    return 1 if value else 0


def _clean_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_payload(payload: dict) -> dict:
    normalized = dict(payload)
    normalized["codigo"] = _clean_str(normalized.get("codigo"))
    normalized["nombre"] = _clean_str(normalized.get("nombre"))
    normalized["contacto_nombre"] = _clean_str(normalized.get("contacto_nombre"))
    normalized["email"] = _clean_str(normalized.get("email"))
    normalized["telefono"] = _clean_str(normalized.get("telefono"))
    normalized["cuit"] = _clean_str(normalized.get("cuit"))
    normalized["direccion"] = _clean_str(normalized.get("direccion"))
    normalized["localidad"] = _clean_str(normalized.get("localidad"))
    normalized["provincia"] = _clean_str(normalized.get("provincia"))
    normalized["notas"] = _clean_str(normalized.get("notas"))
    return normalized


def listar_proveedores(
    db: Session,
    q: Optional[str] = None,
    activo: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    filtros: list[str] = []
    params: dict = {"limit": limit, "offset": offset}

    if q:
        filtros.append("(p.codigo LIKE :q OR p.nombre LIKE :q OR p.contacto_nombre LIKE :q)")
        params["q"] = f"%{q.strip()}%"

    if activo is not None:
        filtros.append("p.activo = :activo")
        params["activo"] = _to_bool_sql(activo)

    where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    sql = f"""
        SELECT
            p.id,
            p.codigo,
            p.nombre,
            p.contacto_nombre,
            p.email,
            p.telefono,
            p.cuit,
            p.direccion,
            p.localidad,
            p.provincia,
            p.notas,
            p.activo,
            p.fecha_creacion,
            p.fecha_actualizacion
        FROM proveedor p
        {where}
        ORDER BY p.nombre ASC, p.codigo ASC
        LIMIT :limit OFFSET :offset
    """
    rows = db.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def obtener_proveedor(db: Session, proveedor_id: int) -> Optional[dict]:
    row = db.execute(
        text(
            """
            SELECT
                p.id,
                p.codigo,
                p.nombre,
                p.contacto_nombre,
                p.email,
                p.telefono,
                p.cuit,
                p.direccion,
                p.localidad,
                p.provincia,
                p.notas,
                p.activo,
                p.fecha_creacion,
                p.fecha_actualizacion
            FROM proveedor p
            WHERE p.id = :id
            """
        ),
        {"id": proveedor_id},
    ).mappings().first()
    return dict(row) if row else None


def existe_codigo(
    db: Session,
    codigo: str,
    exclude_id: Optional[int] = None,
) -> bool:
    sql = "SELECT id FROM proveedor WHERE codigo = :codigo"
    params: dict[str, object] = {"codigo": codigo}
    if exclude_id is not None:
        sql += " AND id <> :exclude_id"
        params["exclude_id"] = exclude_id
    return db.execute(text(sql), params).first() is not None


def crear_proveedor(db: Session, data: dict) -> dict:
    payload = _normalize_payload(data)
    if not payload.get("codigo"):
        raise ValueError("codigo es obligatorio")
    if not payload.get("nombre"):
        raise ValueError("nombre es obligatorio")

    if existe_codigo(db, payload["codigo"]):
        raise ValueError("El codigo de proveedor ya existe")

    db.execute(
        text(
            """
            INSERT INTO proveedor (
                codigo,
                nombre,
                contacto_nombre,
                email,
                telefono,
                cuit,
                direccion,
                localidad,
                provincia,
                notas,
                activo
            ) VALUES (
                :codigo,
                :nombre,
                :contacto_nombre,
                :email,
                :telefono,
                :cuit,
                :direccion,
                :localidad,
                :provincia,
                :notas,
                :activo
            )
            """
        ),
        {
            "codigo": payload["codigo"],
            "nombre": payload["nombre"],
            "contacto_nombre": payload.get("contacto_nombre"),
            "email": payload.get("email"),
            "telefono": payload.get("telefono"),
            "cuit": payload.get("cuit"),
            "direccion": payload.get("direccion"),
            "localidad": payload.get("localidad"),
            "provincia": payload.get("provincia"),
            "notas": payload.get("notas"),
            "activo": _to_bool_sql(bool(payload.get("activo", True))),
        },
    )
    proveedor_id_raw = db.execute(text("SELECT LAST_INSERT_ID() AS id")).scalar()
    if proveedor_id_raw is None:
        raise ValueError("No se pudo crear el proveedor")
    proveedor_id = int(proveedor_id_raw)
    created = obtener_proveedor(db, proveedor_id)
    if not created:
        raise ValueError("No se pudo crear el proveedor")
    return created


def actualizar_proveedor(db: Session, proveedor_id: int, data: dict) -> Optional[dict]:
    payload = _normalize_payload(data)
    actual = obtener_proveedor(db, proveedor_id)
    if not actual:
        return None

    codigo = payload.get("codigo")
    nombre = payload.get("nombre")

    if codigo is not None and not codigo:
        raise ValueError("codigo es obligatorio")
    if nombre is not None and not nombre:
        raise ValueError("nombre es obligatorio")

    codigo_final = codigo if codigo is not None else actual["codigo"]
    if existe_codigo(db, codigo_final, exclude_id=proveedor_id):
        raise ValueError("El codigo de proveedor ya existe")

    sets = []
    params = {"id": proveedor_id}

    required_fields = ("codigo", "nombre")
    nullable_fields = ("contacto_nombre", "email", "telefono", "cuit", "direccion", "localidad", "provincia", "notas")

    for field in required_fields:
        if field in payload and payload[field] is not None:
            sets.append(f"{field} = :{field}")
            params[field] = payload[field]

    for field in nullable_fields:
        if field in payload:
            sets.append(f"{field} = :{field}")
            params[field] = payload[field]

    if "activo" in payload and payload["activo"] is not None:
        sets.append("activo = :activo")
        params["activo"] = _to_bool_sql(bool(payload["activo"]))

    if not sets:
        return actual

    db.execute(
        text(f"UPDATE proveedor SET {', '.join(sets)} WHERE id = :id"),
        params,
    )
    return obtener_proveedor(db, proveedor_id)


def eliminar_proveedor(db: Session, proveedor_id: int) -> bool:
    found = db.execute(
        text("SELECT id FROM proveedor WHERE id = :id"),
        {"id": proveedor_id},
    ).first()
    if not found:
        return False
    db.execute(text("DELETE FROM proveedor WHERE id = :id"), {"id": proveedor_id})
    return True
