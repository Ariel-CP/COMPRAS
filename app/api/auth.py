from datetime import datetime, timezone
from typing import Any

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps_auth import get_current_user
from app.core.config import get_settings
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    Permission,
    SessionInfo,
    UserPublic,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _to_user_public(user: dict[str, Any]) -> UserPublic:
    perms_dict = {
        key: Permission(
            puede_leer=bool(values[0]), puede_escribir=bool(values[1])
        )
        for key, values in user.get("permissions", {}).items()
    }
    return UserPublic(
        id=int(user["id"]),
        email=str(user["email"]),
        nombre=user.get("nombre"),
        roles=user.get("roles", []),
        permissions=perms_dict,
    )


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    email = str(payload.email)
    pwd = payload.password

    # Mensaje genérico para evitar enumeración de usuarios.
    user = auth_service.get_user_by_email(db, email)
    pwd_ok = False
    if user and user.get("activo"):
        password_hash = str(user.get("password_hash") or "")
        pwd_ok = auth_service.verify_password(pwd, password_hash)
    else:
        # Ejecuta verify con hash fijo para reducir diferencias de timing.
        try:
            auth_service.verify_password(pwd, "$2b$12$invalidinvalidinvalidinvalidinvA")
        except ValueError:
            pass

    if not (user and user.get("activo") and pwd_ok):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[
                {
                    "loc": ["body", "__all__"],
                    "msg": "Credenciales inválidas.",
                    "type": "value_error",
                }
            ],
        )

    user["roles"] = auth_service.get_user_roles(db, int(user["id"]))
    user["permissions"] = auth_service.get_permissions(db, int(user["id"]))

    token = auth_service.create_access_token(str(user["id"]))
    try:
        payload_dec = jwt.decode(token, settings.auth_secret_key, algorithms=["HS256"])
        jti = payload_dec.get("jti")
        exp_raw = payload_dec.get("exp")
        if exp_raw is None:
            raise ValueError("Missing exp in token payload")
        exp_ts = int(exp_raw)
        expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
    except (jwt.PyJWTError, TypeError, ValueError):
        jti = None
        expires_at = datetime.now(timezone.utc)

    if payload.remember_me:
        max_age = int(settings.auth_remember_days) * 24 * 3600
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            secure=settings.auth_cookie_secure,
            samesite="lax",
            path="/",
            max_age=max_age,
        )
    else:
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            secure=settings.auth_cookie_secure,
            samesite="lax",
            path="/",
        )

    try:
        if jti:
            ip = request.client.host if request.client else None
            ua = request.headers.get("user-agent")
            device = request.headers.get("x-device-name")
            auth_service.create_session(
                db,
                int(user["id"]),
                jti,
                expires_at,
                bool(payload.remember_me),
                ip,
                ua,
                device,
            )
    except (TypeError, ValueError):
        # No bloquear login por error en registro de sesión.
        pass

    return LoginResponse(access_token=token, user=_to_user_public(user))


@router.get("/me", response_model=MeResponse)
def me(current_user=Depends(get_current_user)):
    return _to_user_public(current_user)


@router.get("/sessions", response_model=list[SessionInfo])
def list_sessions(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = auth_service.list_sessions_for_user(db, int(current_user["id"]))

    def _iso_or_none(value: Any) -> str | None:
        return value.isoformat() if hasattr(value, "isoformat") else None

    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "jti": str(r.get("jti") or ""),
                "created_at": _iso_or_none(r.get("created_at")) or "",
                "last_used_at": _iso_or_none(r.get("last_used_at")),
                "expires_at": _iso_or_none(r.get("expires_at")) or "",
                "persistent": bool(r.get("persistent")),
                "revoked": bool(r.get("revoked")),
                "ip": r.get("ip"),
                "user_agent": r.get("user_agent"),
                "device_name": r.get("device_name"),
            }
        )
    return out


@router.delete("/sessions/{jti}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    jti: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sess = auth_service.get_session_by_jti(db, jti)
    sess_user_id = sess.get("user_id") if sess else None
    if sess is None or sess_user_id is None or int(sess_user_id) != int(current_user["id"]):
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    auth_service.revoke_session(db, jti)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    response.set_cookie(
        key="access_token",
        value="",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=0,
        path="/",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
