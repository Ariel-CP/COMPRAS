from typing import List, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.services import auth_service


PERMISSION_CATALOG: tuple[tuple[str, str], ...] = (
    ("admin_backups", "Administracion de backups"),
    ("admin_roles", "Administracion de roles"),
    ("admin_usuarios", "Administracion de usuarios"),
    ("informes", "Informes"),
    ("mbom", "MBOM"),
    ("plan", "Plan de produccion"),
    ("precios", "Precios"),
    ("productos", "Articulos"),
    ("rubros", "Rubros"),
    ("stock", "Stock"),
    ("tipo_cambio", "Tipo de cambio"),
    ("unidades", "Unidades"),
)

LEGACY_PERMISSION_ALIASES: dict[str, str] = {
    "producto": "productos",
    "plan_produccion_mensual": "plan",
    "stock_disponible_mes": "stock",
}


def list_permission_catalog() -> List[dict]:
    return [{"form_key": fk, "label": label} for fk, label in PERMISSION_CATALOG]


def _normalize_form_key(form_key: str) -> str:
    key = (form_key or "").strip()
    if not key:
        return ""
    return LEGACY_PERMISSION_ALIASES.get(key, key)


def list_users(
    db: Session,
    q: Optional[str] = None,
    activo: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[dict]:
    filtros = []
    params = {}
    if q:
        filtros.append("(u.email LIKE :q OR u.nombre LIKE :q)")
        params["q"] = f"%{q}%"
    if activo is not None:
        filtros.append("u.activo = :activo")
        params["activo"] = 1 if activo else 0
    where = "WHERE " + " AND ".join(filtros) if filtros else ""
    sql = f"""
        SELECT u.id, u.email, u.nombre, u.activo, u.fecha_creacion
        FROM usuario u
        {where}
        ORDER BY u.fecha_creacion DESC
        LIMIT :limit OFFSET :offset
    """
    params.update({"limit": limit, "offset": offset})
    rows = db.execute(text(sql), params).mappings().all()
    user_ids = [r["id"] for r in rows]
    roles_map = _get_roles_for_users(db, user_ids) if user_ids else {}
    result = []
    for r in rows:
        user = dict(r)
        fc = user.get("fecha_creacion")
        if fc is not None:
            user["fecha_creacion"] = fc.isoformat() if hasattr(fc, "isoformat") else fc
        user["roles"] = roles_map.get(r["id"], [])
        result.append(user)
    return result


def get_user(db: Session, user_id: int) -> Optional[dict]:
    row = db.execute(
        text(
            "SELECT id, email, nombre, activo, fecha_creacion FROM usuario WHERE id = :id"
        ),
        {"id": user_id},
    ).mappings().first()
    if not row:
        return None
    user = dict(row)
    fc = user.get("fecha_creacion")
    if fc is not None:
        user["fecha_creacion"] = fc.isoformat() if hasattr(fc, "isoformat") else fc
    user["roles"] = _get_roles_for_users(db, [user_id]).get(user_id, [])
    return user


def create_user(
    db: Session,
    email: str,
    nombre: str,
    password: str,
    activo: bool,
    roles: Optional[List[str]] = None,
) -> dict:
    hashed = auth_service.hash_password(password)
    res = db.execute(
        text(
            "INSERT INTO usuario (email, nombre, password_hash, activo) "
            "VALUES (:email, :nombre, :phash, :activo)"
        ),
        {
            "email": email,
            "nombre": nombre,
            "phash": hashed,
            "activo": 1 if activo else 0,
        },
    )
    user_id = res.lastrowid  # type: ignore[attr-defined]
    if not user_id:
        user_id = db.execute(text("SELECT LAST_INSERT_ID() AS id")).scalar()
    if roles:
        _sync_roles(db, int(user_id), roles)
    return get_user(db, int(user_id))  # type: ignore[arg-type]


def update_user(
    db: Session,
    user_id: int,
    nombre: Optional[str] = None,
    password: Optional[str] = None,
    activo: Optional[bool] = None,
    roles: Optional[List[str]] = None,
) -> Optional[dict]:
    sets = []
    params = {"id": user_id}
    if nombre is not None:
        sets.append("nombre = :nombre")
        params["nombre"] = nombre
    if password is not None:
        sets.append("password_hash = :phash")
        params["phash"] = auth_service.hash_password(password)
    if activo is not None:
        sets.append("activo = :activo")
        params["activo"] = 1 if activo else 0
    if sets:
        sql = "UPDATE usuario SET " + ", ".join(sets) + " WHERE id = :id"
        db.execute(text(sql), params)
    if roles is not None:
        _sync_roles(db, user_id, roles)
    return get_user(db, user_id)


def deactivate_user(db: Session, user_id: int) -> None:
    db.execute(
        text("UPDATE usuario SET activo = 0 WHERE id = :id"), {"id": user_id}
    )


def list_roles(db: Session) -> List[dict]:
    rows = db.execute(
        text(
            "SELECT r.id, r.nombre, r.descripcion, "
            "(SELECT COUNT(*) FROM usuario_rol ur WHERE ur.rol_id = r.id) as user_count "
            "FROM rol r ORDER BY r.nombre"
        )
    ).mappings().all()
    return [dict(r) for r in rows]


def get_role(db: Session, rol_id: int) -> Optional[dict]:
    row = db.execute(
        text(
            "SELECT r.id, r.nombre, r.descripcion, "
            "(SELECT COUNT(*) FROM usuario_rol ur WHERE ur.rol_id = r.id) as user_count "
            "FROM rol r WHERE r.id = :id"
        ),
        {"id": rol_id},
    ).mappings().first()
    return dict(row) if row else None


def create_role(db: Session, nombre: str, descripcion: Optional[str]) -> dict:
    res = db.execute(
        text("INSERT INTO rol (nombre, descripcion) VALUES (:n, :d)"),
        {"n": nombre, "d": descripcion},
    )
    rid = res.lastrowid  # type: ignore[attr-defined]
    if not rid:
        rid = db.execute(text("SELECT LAST_INSERT_ID() AS id")).scalar()
    return get_role(db, int(rid))  # type: ignore[arg-type]


def update_role(
    db: Session, rol_id: int, nombre: Optional[str], descripcion: Optional[str]
) -> Optional[dict]:
    sets = []
    params = {"id": rol_id}
    if nombre is not None:
        sets.append("nombre = :nombre")
        params["nombre"] = nombre
    if descripcion is not None:
        sets.append("descripcion = :desc")
        params["desc"] = descripcion
    if sets:
        db.execute(text("UPDATE rol SET " + ", ".join(sets) + " WHERE id = :id"), params)
    return get_role(db, rol_id)


def delete_role(db: Session, rol_id: int) -> None:
    count = db.execute(
        text("SELECT COUNT(*) FROM usuario_rol WHERE rol_id = :id"), {"id": rol_id}
    ).scalar()
    if count and int(count) > 0:
        raise ValueError("No se puede borrar: el rol tiene usuarios asociados")
    db.execute(text("DELETE FROM permiso_form WHERE rol_id = :id"), {"id": rol_id})
    db.execute(text("DELETE FROM rol WHERE id = :id"), {"id": rol_id})


def get_role_perms(db: Session, rol_id: int) -> List[dict]:
    rows = db.execute(
        text(
            "SELECT id, form_key, puede_leer, puede_escribir "
            "FROM permiso_form WHERE rol_id = :rid ORDER BY form_key"
        ),
        {"rid": rol_id},
    ).mappings().all()
    merged: dict[str, dict] = {}
    for r in rows:
        row = dict(r)
        normalized = _normalize_form_key(str(row.get("form_key", "")))
        if not normalized:
            continue
        if normalized not in merged:
            row["form_key"] = normalized
            merged[normalized] = row
            continue
        merged_row = merged[normalized]
        merged_row["puede_leer"] = bool(merged_row.get("puede_leer")) or bool(
            row.get("puede_leer")
        )
        merged_row["puede_escribir"] = bool(merged_row.get("puede_escribir")) or bool(
            row.get("puede_escribir")
        )
    return sorted(merged.values(), key=lambda x: str(x.get("form_key", "")))


def set_role_perms(db: Session, rol_id: int, perms: List[dict]) -> List[dict]:
    valid_keys = {fk for fk, _ in PERMISSION_CATALOG}
    normalized_perms: dict[str, dict] = {}
    invalid_keys: list[str] = []

    for p in perms:
        normalized_key = _normalize_form_key(str(p.get("form_key", "")))
        if not normalized_key:
            continue
        if normalized_key not in valid_keys:
            invalid_keys.append(str(p.get("form_key", "")))
            continue

        prev = normalized_perms.get(normalized_key)
        current = {
            "form_key": normalized_key,
            "puede_leer": bool(p.get("puede_leer", True)),
            "puede_escribir": bool(p.get("puede_escribir", False)),
        }
        if prev is None:
            normalized_perms[normalized_key] = current
        else:
            prev["puede_leer"] = prev["puede_leer"] or current["puede_leer"]
            prev["puede_escribir"] = prev["puede_escribir"] or current["puede_escribir"]

    if invalid_keys:
        invalid_list = ", ".join(sorted(set(invalid_keys)))
        raise ValueError(f"form_key invalido: {invalid_list}")

    db.execute(text("DELETE FROM permiso_form WHERE rol_id = :rid"), {"rid": rol_id})
    if normalized_perms:
        insert_sql = text(
            "INSERT INTO permiso_form (rol_id, form_key, puede_leer, puede_escribir) "
            "VALUES (:rid, :fk, :pl, :pe)"
        )
        db.execute(
            insert_sql,
            [
                {
                    "rid": rol_id,
                    "fk": p["form_key"],
                    "pl": 1 if p.get("puede_leer", True) else 0,
                    "pe": 1 if p.get("puede_escribir", False) else 0,
                }
                for p in normalized_perms.values()
            ],
        )
    return get_role_perms(db, rol_id)


def _sync_roles(db: Session, user_id: int, roles: List[str]) -> None:
    role_ids = []
    for r in roles:
        rid = auth_service.ensure_role(db, r)
        role_ids.append(rid)
    if role_ids:
        delete_stmt = (
            text(
                "DELETE FROM usuario_rol WHERE usuario_id = :uid AND rol_id NOT IN :rids"
            )
            .bindparams(bindparam("rids", expanding=True))
        )
        db.execute(delete_stmt, {"uid": user_id, "rids": role_ids})
    else:
        db.execute(
            text("DELETE FROM usuario_rol WHERE usuario_id = :uid"),
            {"uid": user_id},
        )
    for rid in role_ids:
        db.execute(
            text(
                "INSERT IGNORE INTO usuario_rol (usuario_id, rol_id) VALUES (:uid, :rid)"
            ),
            {"uid": user_id, "rid": rid},
        )


def _get_roles_for_users(db: Session, user_ids: List[int]) -> dict:
    if not user_ids:
        return {}
    stmt = (
        text(
            "SELECT ur.usuario_id, r.nombre "
            "FROM usuario_rol ur JOIN rol r ON r.id = ur.rol_id "
            "WHERE ur.usuario_id IN :ids"
        )
        .bindparams(bindparam("ids", expanding=True))
    )
    rows = db.execute(stmt, {"ids": user_ids}).fetchall()
    result: dict[int, List[str]] = {}
    for uid, rol_nombre in rows:
        result.setdefault(int(uid), []).append(rol_nombre)
    return result
