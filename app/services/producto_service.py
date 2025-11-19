from typing import Any, Dict, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session


TIPO_VALUES = {"PT", "WIP", "MP", "EMB", "SERV", "HERR"}


def _row_to_producto(row: Any) -> Dict[str, Any]:
    return {
        "id": row.id,
        "codigo": row.codigo,
        "nombre": row.nombre,
        "tipo_producto": row.tipo_producto,
        "unidad_medida_id": row.unidad_medida_id,
        "activo": bool(row.activo),
    }


def _ensure_um_exists(db: Session, um_id: int) -> None:
    r = db.execute(
        text("SELECT id FROM unidad_medida WHERE id=:id"),
        {"id": um_id},
    ).first()
    if not r:
        raise ValueError("La unidad de medida no existe")


def listar_productos(
    db: Session,
    q: Optional[str] = None,
    tipo: Optional[str] = None,
    activo: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    where = ["1=1"]
    params: Dict[str, Any] = {"limit": limit, "offset": offset}
    if q:
        where.append("(codigo LIKE :q OR nombre LIKE :q)")
        params["q"] = f"%{q}%"
    if tipo:
        if tipo not in TIPO_VALUES:
            raise ValueError("tipo_producto inválido")
        where.append("tipo_producto = :tipo")
        params["tipo"] = tipo
    if activo is not None:
        where.append("activo = :activo")
        params["activo"] = 1 if activo else 0

    sql = text(
        "SELECT id, codigo, nombre, tipo_producto, unidad_medida_id, activo "
        "FROM producto WHERE "
        + " AND ".join(where)
        + " ORDER BY codigo LIMIT :limit OFFSET :offset"
    )
    rows = db.execute(sql, params).fetchall()
    return [_row_to_producto(r) for r in rows]


def get_producto(db: Session, prod_id: int) -> Optional[Dict[str, Any]]:
    row = db.execute(
        text(
            "SELECT id, codigo, nombre, tipo_producto, "
            "unidad_medida_id, activo FROM producto WHERE id=:id"
        ),
        {"id": prod_id},
    ).first()
    return _row_to_producto(row) if row else None


def crear_producto(
    db: Session,
    codigo: str,
    nombre: str,
    tipo_producto: str,
    unidad_medida_id: int,
    activo: bool = True,
) -> Dict[str, Any]:
    if tipo_producto not in TIPO_VALUES:
        raise ValueError("tipo_producto inválido")
    _ensure_um_exists(db, unidad_medida_id)

    # Verificar unicidad de codigo
    dup = db.execute(
        text("SELECT id FROM producto WHERE codigo=:c"),
        {"c": codigo},
    ).first()
    if dup:
        raise ValueError("El código de producto ya existe")

    res = db.execute(
        text(
            "INSERT INTO producto (codigo, nombre, tipo_producto, "
            "unidad_medida_id, activo) VALUES (:codigo, :nombre, :tipo, :um, "
            ":activo)"
        ),
        {
            "codigo": codigo,
            "nombre": nombre,
            "tipo": tipo_producto,
            "um": unidad_medida_id,
            "activo": 1 if activo else 0,
        },
    )
    new_id = getattr(res, "lastrowid", None)
    if not new_id:
        new_id = db.execute(text("SELECT LAST_INSERT_ID()"))
        new_id = new_id.scalar() if new_id else None
    if new_id is None:
        raise ValueError("No se pudo obtener el ID del nuevo producto")
    return get_producto(db, int(new_id))  # type: ignore[return-value]


def actualizar_producto(
    db: Session,
    prod_id: int,
    codigo: str,
    nombre: str,
    tipo_producto: str,
    unidad_medida_id: int,
    activo: bool,
) -> Dict[str, Any]:
    if tipo_producto not in TIPO_VALUES:
        raise ValueError("tipo_producto inválido")
    _ensure_um_exists(db, unidad_medida_id)

    # Chequear existencia
    base = get_producto(db, prod_id)
    if not base:
        raise ValueError("Producto no encontrado")

    # Verificar unicidad de codigo al actualizar
    dup = db.execute(
        text("SELECT id FROM producto WHERE codigo=:c AND id<>:id"),
        {"c": codigo, "id": prod_id},
    ).first()
    if dup:
        raise ValueError("El código de producto ya existe")

    db.execute(
        text(
            "UPDATE producto SET codigo=:codigo, nombre=:nombre, "
            "tipo_producto=:tipo, unidad_medida_id=:um, activo=:activo "
            "WHERE id=:id"
        ),
        {
            "codigo": codigo,
            "nombre": nombre,
            "tipo": tipo_producto,
            "um": unidad_medida_id,
            "activo": 1 if activo else 0,
            "id": prod_id,
        },
    )
    return get_producto(db, prod_id)  # type: ignore[return-value]
