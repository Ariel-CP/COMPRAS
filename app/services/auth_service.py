from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import jwt
import uuid
from passlib.context import CryptContext  # type: ignore[import-untyped]
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_access_token(
    subject: str,
    expires_minutes: Optional[int] = None,
) -> str:
    expire_minutes = expires_minutes or settings.auth_access_token_minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    jti = uuid.uuid4().hex
    to_encode = {"sub": subject, "exp": int(expire.timestamp()), "jti": jti}
    return jwt.encode(to_encode, settings.auth_secret_key, algorithm="HS256")


def get_user_by_email(db: Session, email: str) -> Optional[dict]:
    row = db.execute(
        text(
            "SELECT id, email, nombre, password_hash, activo "
            "FROM usuario WHERE email = :email"
        ),
        {"email": email},
    ).mappings().first()
    return dict(row) if row else None


def get_user_by_id(db: Session, user_id: int) -> Optional[dict]:
    row = db.execute(
        text(
            "SELECT id, email, nombre, password_hash, activo "
            "FROM usuario WHERE id = :id"
        ),
        {"id": user_id},
    ).mappings().first()
    return dict(row) if row else None


def authenticate_user(db: Session, email: str, password: str) -> Optional[dict]:
    user = get_user_by_email(db, email)
    if not user or not user.get("activo"):
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def create_user(
    db: Session,
    email: str,
    nombre: str,
    password: str,
    roles: Optional[List[str]] = None,
) -> dict:
    hashed = hash_password(password)
    res = db.execute(
        text(
            "INSERT INTO usuario (email, nombre, password_hash, activo) "
            "VALUES (:email, :nombre, :phash, 1)"
        ),
        {"email": email, "nombre": nombre, "phash": hashed},
    )
    user_id = res.lastrowid  # type: ignore[attr-defined]
    if not user_id:
        user_id = db.execute(text("SELECT LAST_INSERT_ID() AS id")).scalar()
    if roles:
        for rol_nombre in roles:
            rol_id = ensure_role(db, rol_nombre)
            db.execute(
                text(
                    "INSERT IGNORE INTO usuario_rol (usuario_id, rol_id) "
                    "VALUES (:uid, :rid)"
                ),
                {"uid": user_id, "rid": rol_id},
            )
    created_user = get_user_by_id(db, int(user_id))
    if created_user is None:
        raise RuntimeError("No se pudo recuperar el usuario creado")
    return created_user


def ensure_role(db: Session, nombre: str) -> int:
    row = db.execute(
        text("SELECT id FROM rol WHERE nombre = :n"), {"n": nombre}
    ).scalar()
    if row:
        return int(row)
    res = db.execute(
        text("INSERT INTO rol (nombre, descripcion) VALUES (:n, :d)"),
        {"n": nombre, "d": None},
    )
    rid = res.lastrowid  # type: ignore[attr-defined]
    if not rid:
        rid = db.execute(text("SELECT LAST_INSERT_ID() AS id")).scalar()
    return int(rid)


def _ensure_rol(db: Session, nombre: str) -> int:
    return ensure_role(db, nombre)


def get_user_roles(db: Session, user_id: int) -> List[str]:
    rows = db.execute(
        text(
            "SELECT r.nombre FROM rol r "
            "JOIN usuario_rol ur ON ur.rol_id = r.id "
            "WHERE ur.usuario_id = :uid"
        ),
        {"uid": user_id},
    ).fetchall()
    return [r[0] for r in rows]


def get_permissions(db: Session, user_id: int) -> Dict[str, Tuple[bool, bool]]:
    rows = db.execute(
        text(
            "SELECT pf.form_key, pf.puede_leer, pf.puede_escribir "
            "FROM permiso_form pf "
            "JOIN usuario_rol ur ON ur.rol_id = pf.rol_id "
            "WHERE ur.usuario_id = :uid"
        ),
        {"uid": user_id},
    ).fetchall()
    perms: Dict[str, Tuple[bool, bool]] = {}
    for form_key, leer, escribir in rows:
        if form_key not in perms:
            perms[form_key] = (bool(leer), bool(escribir))
        else:
            old_read, old_write = perms[form_key]
            perms[form_key] = (old_read or bool(leer), old_write or bool(escribir))

    # Compatibilidad: si el usuario ya es admin por roles/usuarios,
    # habilitar acceso al modulo de backups aunque aun no tenga form_key explicita.
    admin_users_read, admin_users_write = perms.get("admin_usuarios", (False, False))
    admin_roles_read, admin_roles_write = perms.get("admin_roles", (False, False))
    inferred_read = admin_users_read or admin_roles_read
    inferred_write = admin_users_write or admin_roles_write
    backup_read, backup_write = perms.get("admin_backups", (False, False))
    if inferred_read or inferred_write:
        perms["admin_backups"] = (
            backup_read or inferred_read,
            backup_write or inferred_write,
        )

    return perms


def user_has_permission(
    db: Session, user_id: int, form_key: str, requires_write: bool = False
) -> bool:
    perms = get_permissions(db, user_id)
    if form_key not in perms:
        return False
    can_read, can_write = perms[form_key]
    return can_write if requires_write else can_read


def create_session(
    db: Session,
    user_id: int,
    jti: str,
    expires_at: datetime,
    persistent: bool = False,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    device_name: Optional[str] = None,
) -> None:
    """Inserta una sesión en la tabla `user_session`. Commit dentro."""
    db.execute(
        text(
            "INSERT INTO user_session ("
            "user_id, jti, created_at, expires_at, persistent, ip, "
            "user_agent, device_name, revoked"
            ") VALUES (:uid, :jti, CURRENT_TIMESTAMP, :exp, :persistent, :ip, :ua, :dn, 0)"
        ),
        {
            "uid": user_id,
            "jti": jti,
            "exp": expires_at.strftime("%Y-%m-%d %H:%M:%S"),
            "persistent": 1 if persistent else 0,
            "ip": ip,
            "ua": user_agent,
            "dn": device_name,
        },
    )
    db.commit()


def revoke_session(db: Session, jti: str) -> None:
    db.execute(text("UPDATE user_session SET revoked=1 WHERE jti=:jti"), {"jti": jti})
    db.commit()


def get_session_by_jti(db: Session, jti: str) -> Optional[dict]:
    row = db.execute(
        text(
            "SELECT id,user_id,jti,created_at,last_used_at,expires_at,persistent,revoked,ip,user_agent,device_name "
            "FROM user_session WHERE jti=:jti"
        ),
        {"jti": jti},
    ).mappings().first()
    return dict(row) if row else None


def list_sessions_for_user(db: Session, user_id: int) -> List[dict]:
    rows = db.execute(
        text(
            "SELECT id,user_id,jti,created_at,last_used_at,expires_at,persistent,revoked,ip,user_agent,device_name "
            "FROM user_session WHERE user_id=:uid ORDER BY created_at DESC"
        ),
        {"uid": user_id},
    ).mappings().all()
    return [dict(r) for r in rows]
