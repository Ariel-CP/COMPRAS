from typing import Callable

import jwt
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.services import auth_service

settings = get_settings()


def _decode_subject_from_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.auth_secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado"
        ) from None
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido"
        ) from None

    subject = payload.get("sub")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin sujeto",
        )
    return str(subject)


def get_current_user(
    request: Request, db: Session = Depends(get_db)
):  # -> dict[str, object]:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
        )
    try:
        payload = jwt.decode(token, settings.auth_secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado") from None
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido") from None

    user_id = payload.get("sub")
    jti = payload.get("jti")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sin sujeto")
    user = auth_service.get_user_by_id(db, int(user_id))
    if not user or not user.get("activo"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo o inexistente",
        )

    # verificar sesión/ jti
    if not jti:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sin jti")
    sess = auth_service.get_session_by_jti(db, jti)
    if not sess or bool(sess.get("revoked")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión inválida")
    # comprobar expiración de sesión
    exp = sess.get("expires_at")
    if exp and isinstance(exp, datetime):
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión expirada")
    # actualizar last_used_at (no bloqueo)
    try:
        db.execute("UPDATE user_session SET last_used_at=CURRENT_TIMESTAMP WHERE jti=:jti", {"jti": jti})
        db.commit()
    except Exception:
        db.rollback()

    roles = auth_service.get_user_roles(db, user["id"])
    permissions = auth_service.get_permissions(db, user["id"])
    user["roles"] = roles
    user["permissions"] = permissions
    return user


def get_current_user_optional(request: Request, db: Session = Depends(get_db)):
    """Devuelve el usuario autenticado o None si no hay token/usuario válido.

    No lanza HTTPException; se usa para renderizar vistas públicas que quieren
    conocer al usuario si existe, sin forzar autenticación.
    """
    # Reusable helper: decode current user from cookie without raising
    return decode_current_user_from_cookie(request, db)


def decode_current_user_from_cookie(request: Request, db: Session):
    """Decodifica el token `access_token` desde la cookie y devuelve el
    usuario con roles y permisos, o `None` si no existe/ es inválido.

    Esta función no lanza HTTPException; es útil para middleware y vistas
    públicas que sólo quieren conocer si hay sesión.
    """
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.auth_secret_key, algorithms=["HS256"])
    except Exception:
        return None

    user_id = payload.get("sub")
    jti = payload.get("jti")
    if not user_id:
        return None

    user = auth_service.get_user_by_id(db, int(user_id))
    if not user or not user.get("activo"):
        return None
    # validar sesión jti
    if not jti:
        return None
    sess = auth_service.get_session_by_jti(db, jti)
    if not sess or bool(sess.get("revoked")):
        return None
    # comprobar expiración
    exp = sess.get("expires_at")
    try:
        if exp and exp < datetime.now(timezone.utc):
            return None
    except Exception:
        pass
    roles = auth_service.get_user_roles(db, user["id"])
    permissions = auth_service.get_permissions(db, user["id"])
    user["roles"] = roles
    user["permissions"] = permissions
    return user


def require_permission(form_key: str, requires_write: bool = False) -> Callable:
    def _checker(current_user=Depends(get_current_user)):
        perms = current_user.get("permissions", {})
        can_read, can_write = perms.get(form_key, (False, False))
        allowed = can_write if requires_write else can_read
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permiso insuficiente",
            )
        return current_user

    return _checker
