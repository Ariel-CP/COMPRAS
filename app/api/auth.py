from fastapi import APIRouter, Depends, HTTPException, Response, status, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps_auth import get_current_user
from app.core.config import get_settings
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    Permission,
    UserPublic,
    SessionInfo,
)
import jwt
from datetime import datetime, timezone
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _to_user_public(user: dict) -> UserPublic:
    perms_dict = {
        key: Permission(
            puede_leer=bool(values[0]), puede_escribir=bool(values[1])
        )
        for key, values in user.get("permissions", {}).items()
    }
    return UserPublic(
        id=user["id"],
        email=user["email"],
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
    # request added below to capture IP/UA for session; keep db dependency before
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    # Validación más explícita para retornar errores por campo (compatible con frontend)
    email = getattr(payload, "email", None)
    pwd = getattr(payload, "password", None)

    # Intento de login: devolver mensaje genérico para evitar enumeración de usuarios.
    user = auth_service.get_user_by_email(db, email)
    pwd_ok = False
    if user and user.get("activo"):
        pwd_ok = auth_service.verify_password(pwd, user.get("password_hash", ""))
    else:
        # En caso de usuario inexistente o inactivo, ejecutar verify_password
        # contra un hash fijo para reducir diferencias de timing.
        try:
            auth_service.verify_password(pwd, "$2b$12$invalidinvalidinvalidinvalidinvA")
        except Exception:
            # ignorar cualquier error del verificador
            pass

    if not (user and user.get("activo") and pwd_ok):
        # Mensaje genérico para credenciales inválidas
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[{"loc": ["body", "__all__"], "msg": "Credenciales inválidas.", "type": "value_error"}],
        )

    user["roles"] = auth_service.get_user_roles(db, user["id"])
    user["permissions"] = auth_service.get_permissions(db, user["id"])

    # crear token (auth_service genera un `jti` internamente)
    token = auth_service.create_access_token(str(user["id"]))
    # decodificar para extraer jti y exp
    try:
        payload_dec = jwt.decode(token, settings.auth_secret_key, algorithms=["HS256"])
        jti = payload_dec.get("jti")
        exp_ts = int(payload_dec.get("exp"))
        expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
    except Exception:
        # Si algo falla, no crear sesión
        jti = None
        expires_at = datetime.now(timezone.utc)
    # Establecer cookie: persistente si el cliente pidió remember_me
    cookie_params = dict(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    if getattr(payload, "remember_me", False):
        max_age = int(settings.auth_remember_days) * 24 * 3600
        cookie_params["max_age"] = max_age
    # apply cookie
    response.set_cookie(**cookie_params)

    # crear registro de sesión en DB (si jti disponible)
    try:
        if jti:
            # obtener meta desde request
            ip = None
            ua = None
            device = None
            try:
                if request.client:
                    ip = request.client.host
            except Exception:
                ip = None
            ua = request.headers.get("user-agent")
            device = request.headers.get("x-device-name")
            # crear sesión
            auth_service.create_session(
                db,
                int(user["id"]),
                jti,
                expires_at,
                bool(getattr(payload, "remember_me", False)),
                ip,
                ua,
                device,
            )
    except Exception:
        # no bloquear login por error en registro de sesión
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
    # normalizar fechas a ISO
    out = []
    for r in rows:
        out.append(
            {
                "jti": r.get("jti"),
                "created_at": r.get("created_at").isoformat() if r.get("created_at") else None,
                "last_used_at": r.get("last_used_at").isoformat() if r.get("last_used_at") else None,
                "expires_at": r.get("expires_at").isoformat() if r.get("expires_at") else None,
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
    if not sess or int(sess.get("user_id")) != int(current_user["id"]):
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
