from collections.abc import Mapping
from typing import Callable

import jwt
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.services import auth_service

settings = get_settings()

UI_PERMISSION_ROUTES = {
    "/ui/admin/usuarios": ("ui_admin_usuarios", False),
    "/ui/admin/permisos": ("ui_admin_permisos", False),
    "/ui/admin/roles": ("ui_admin_roles", False),
    "/ui/admin/backups": ("ui_admin_backups", False),
    "/ui/admin/logo": ("ui_admin_logo", False),
    "/ui/admin/settings": ("ui_admin_settings", False),
    "/ui/evaluaciones": ("ui_evaluaciones", False),
    "/ui/evaluaciones/ranking": ("ui_evaluaciones_ranking", False),
    "/ui/evaluaciones/ranking-print": ("ui_evaluaciones_ranking_print", False),
    "/ui/evaluaciones/evolucion": ("ui_evaluaciones_evolucion", False),
    "/ui/informes/costos-pt": ("ui_informes_costos_pt", False),
    "/ui/mbom": ("ui_mbom", False),
    "/ui/plan": ("ui_plan", False),
    "/ui/plan-mensual": ("ui_plan_mensual", False),
    "/ui/plan-variaciones": ("ui_plan_variaciones", False),
    "/ui/plan-requerimientos": ("ui_plan_requerimientos", False),
    "/ui/plan-asistente-oc": ("ui_plan_asistente_oc", False),
    "/ui/precios": ("ui_precios", False),
    "/ui/planos-articulos": ("ui_planos_articulos", False),
    "/ui/productos": ("ui_productos", False),
    "/ui/proveedores": ("ui_proveedores", False),
    "/ui/recepcion": ("ui_recepcion", False),
    "/ui/recepcion/controles": ("ui_recepcion_controles", False),
    "/ui/recepcion/calidad": ("ui_recepcion_calidad", False),
    "/ui/recepcion/historial-access": ("ui_recepcion_historial_access", False),
    "/ui/rubros": ("ui_rubros", False),
    "/ui/rubros/nuevo": ("ui_rubros_nuevo", False),
    "/ui/sesiones": ("ui_sesiones", False),
    "/ui/stock": ("ui_stock", False),
    "/ui/tipo-cambio": ("ui_tipo_cambio", False),
}

API_PERMISSION_ROUTES = {
    "/api/backups": (("ui_admin_backups",), None),
    "/api/evaluaciones/ranking-periodo": (("ui_evaluaciones_ranking",), False),
    "/api/evaluaciones/proveedor/": (("ui_evaluaciones_evolucion",), False),
    "/api/evaluaciones": (("ui_evaluaciones",), None),
    "/api/informes": (("ui_informes_costos_pt",), None),
    "/api/mbom": (("ui_mbom",), None),
    "/api/operaciones": (("ui_mbom",), None),
    "/api/plan-produccion-mensual": (
        (
            "ui_plan_mensual",
            "ui_plan_requerimientos",
            "ui_plan_variaciones",
            "ui_plan_asistente_oc",
        ),
        None,
    ),
    "/api/plan": (("ui_plan",), None),
    "/api/precios": (("ui_precios",), None),
    "/api/productos/planos": (("ui_planos_articulos",), False),
    "/api/productos": (("ui_productos", "ui_mbom", "ui_precios"), None),
    "/api/proveedores": (("ui_proveedores", "ui_evaluaciones", "ui_evaluaciones_evolucion"), None),
    "/api/recepcion/access": (("ui_recepcion_historial_access",), None),
    "/api/recepcion/calidad": (("ui_recepcion_calidad",), None),
    "/api/recepcion/controles": (("ui_recepcion_controles",), None),
    "/api/recepcion": (("ui_recepcion",), None),
    "/api/roles": (("ui_admin_roles", "ui_admin_permisos"), None),
    "/api/rubros": (("ui_rubros", "ui_rubros_nuevo", "ui_rubros_editar", "ui_rubros_eliminar"), None),
    "/api/stock": (("ui_stock", "ui_plan_asistente_oc"), None),
    "/api/system/logo": (
        (
            "ui_admin_logo",
            "ui_admin_usuarios",
            "ui_admin_permisos",
            "ui_admin_roles",
            "ui_admin_backups",
            "ui_admin_settings",
        ),
        False,
    ),
    "/api/system": (("ui_admin_settings",), None),
    "/api/tipo-cambio": (("ui_tipo_cambio",), None),
    "/api/unidades": (("ui_productos", "ui_planos_articulos", "ui_mbom", "ui_precios"), False),
    "/api/users": (("ui_admin_usuarios",), None),
}


def resolve_ui_permission(path: str, method: str) -> tuple[str, bool] | None:
    if path.startswith("/ui/rubros/editar/"):
        return "ui_rubros_editar", method not in {"GET", "HEAD"}
    if path.startswith("/ui/rubros/eliminar/"):
        return "ui_rubros_eliminar", method not in {"GET", "HEAD"}
    if path.startswith("/ui/recepcion/calidad/linea/"):
        return "ui_recepcion_calidad", method not in {"GET", "HEAD"}
    permission = UI_PERMISSION_ROUTES.get(path)
    if permission is None:
        return None
    form_key, requires_write = permission
    if path == "/ui/rubros/nuevo" and method not in {"GET", "HEAD"}:
        requires_write = True
    return form_key, requires_write


def _query_requires_write(
    query_params: Mapping[str, str], name: str, default: bool = False,
) -> bool:
    value = query_params.get(name)
    if value is None:
        return default
    # Las formas booleanas válidas coinciden con FastAPI; lo desconocido no rebaja permisos.
    return str(value).strip().lower() not in {"false", "0", "off", "no", "f", "n"}


def resolve_api_permissions(
    path: str,
    method: str,
    query_params=None,
) -> tuple[tuple[str, ...], bool] | None:
    query_params = query_params or {}
    if path in {"/api/roles", "/api/roles/"} and method in {"GET", "HEAD"}:
        return ("ui_admin_roles", "ui_admin_permisos"), False
    if path.startswith("/api/roles/") and path.endswith("/perms"):
        return ("ui_admin_permisos",), method not in {"GET", "HEAD"}
    if path.startswith("/api/roles"):
        return ("ui_admin_roles",), method not in {"GET", "HEAD"}
    if path.startswith("/api/evaluaciones/ranking-periodo"):
        return ("ui_evaluaciones_ranking", "ui_evaluaciones_ranking_print"), False
    if path.startswith("/api/evaluaciones/ranking-operativo"):
        return ("ui_evaluaciones_ranking",), False
    if path.startswith("/api/evaluaciones/proveedor/"):
        return ("ui_evaluaciones_evolucion",), False
    if path.startswith("/api/evaluaciones"):
        return ("ui_evaluaciones",), method not in {"GET", "HEAD"}
    if path.startswith("/api/productos/planos"):
        return ("ui_planos_articulos",), False
    if path.startswith("/api/productos"):
        if method == "POST":
            return ("ui_productos", "ui_mbom"), True
        if method in {"PUT", "DELETE", "PATCH"}:
            return ("ui_productos",), True
        return ("ui_productos", "ui_mbom", "ui_precios"), False
    if path.startswith("/api/proveedores"):
        if method in {"GET", "HEAD"}:
            return ("ui_proveedores", "ui_evaluaciones", "ui_evaluaciones_evolucion"), False
        return ("ui_proveedores",), True
    if path.startswith("/api/recepcion/operativas/lineas-pendientes"):
        return ("ui_recepcion_calidad",), False
    if "/intentos-inspeccion" in path:
        return ("ui_recepcion_calidad",), True
    if path.startswith("/api/recepcion/operativas/") and method in {"GET", "HEAD"}:
        return (
            "ui_recepcion",
            "ui_recepcion_calidad",
            "ui_recepcion_controles",
        ), False
    if path.startswith("/api/recepcion/operativas/") and method in {"PUT", "DELETE", "PATCH"}:
        return ("ui_recepcion", "ui_recepcion_calidad"), True
    if "/control-calidad" in path:
        return ("ui_recepcion_calidad",), True
    if path.startswith("/api/recepcion/access/controles"):
        return ("ui_recepcion_controles",), False
    if path.startswith("/api/recepcion/access"):
        return ("ui_recepcion_historial_access",), False
    if path.startswith("/api/recepcion/controles"):
        return ("ui_recepcion_controles",), method not in {"GET", "HEAD"}
    if path == "/api/rubros" or path == "/api/rubros/":
        key = "ui_rubros_nuevo" if method not in {"GET", "HEAD"} else "ui_rubros"
        return (key,), method not in {"GET", "HEAD"}
    if path.startswith("/api/rubros/"):
        if method in {"GET", "HEAD"}:
            return ("ui_rubros", "ui_rubros_editar", "ui_rubros_eliminar"), False
        if method == "DELETE":
            return ("ui_rubros_eliminar",), True
        return ("ui_rubros_editar",), True
    if path.startswith("/api/informes"):
        return ("ui_informes_costos_pt",), False
    if path.startswith("/api/plan-produccion-mensual"):
        normalized = path.rstrip("/")
        if normalized == "/api/plan-produccion-mensual/asistente-oc/calcular" and method == "POST":
            return ("ui_plan_asistente_oc",), _query_requires_write(query_params, "persistir_sugerencias")
        if normalized == "/api/plan-produccion-mensual/faltantes-capacidad" and method in {"GET", "HEAD"}:
            return ("ui_plan_mensual", "ui_plan_requerimientos"), _query_requires_write(query_params, "persistir_sugerencias")
        if normalized in {
            "/api/plan-produccion-mensual/requerimientos-valuados",
            "/api/plan-produccion-mensual/requerimientos-valuados.xlsx",
        } and method in {"GET", "HEAD"}:
            return ("ui_plan_requerimientos",), _query_requires_write(query_params, "persistir")
        if (
            normalized == "/api/plan-produccion-mensual/asistente-oc/ia"
            and method == "POST"
        ) or (
            normalized == "/api/plan-produccion-mensual/asistente-oc/ia/estado"
            and method in {"GET", "HEAD"}
        ):
            return ("ui_plan_asistente_oc",), False
        if (
            query_params.get("persistir") == "true"
            or query_params.get("persistir_sugerencias") == "true"
            or "faltantes-capacidad" in path
        ):
            return ("ui_plan_requerimientos",), True
        if any(token in path for token in ("requerimiento", "necesidad")):
            return ("ui_plan_requerimientos",), method not in {"GET", "HEAD"}
        if any(token in path for token in ("variacion", "analisis", "ajuste")):
            return ("ui_plan_variaciones",), method not in {"GET", "HEAD"}
        if any(token in path for token in ("asistente", "oc", "orden")):
            return ("ui_plan_asistente_oc",), method not in {"GET", "HEAD"}
        return ("ui_plan_mensual",), method not in {"GET", "HEAD"}

    for route, permission in API_PERMISSION_ROUTES.items():
        if path == route or path.startswith(route + "/") or route.endswith("/") and path.startswith(route):
            keys, requires_write = permission
            return keys, method not in {"GET", "HEAD"} if requires_write is None else requires_write
    return None


def user_is_admin(user: dict) -> bool:
    return any(str(role).strip().casefold() == "admin" for role in user.get("roles", []))


def user_has_permission(user: dict, form_key: str, requires_write: bool = False) -> bool:
    if user_is_admin(user):
        return True
    can_read, can_write = user.get("permissions", {}).get(form_key, (False, False))
    return bool(can_write) if requires_write else bool(can_read or can_write)


def user_has_any_permission(user: dict, form_keys: tuple[str, ...], requires_write: bool = False) -> bool:
    return any(user_has_permission(user, key, requires_write) for key in form_keys)


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
        db.execute(
            text("UPDATE user_session SET last_used_at=CURRENT_TIMESTAMP WHERE jti=:jti"),
            {"jti": jti},
        )
        db.commit()
    except RuntimeError:
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
    except jwt.PyJWTError:
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
    except TypeError:
        pass
    roles = auth_service.get_user_roles(db, user["id"])
    permissions = auth_service.get_permissions(db, user["id"])
    user["roles"] = roles
    user["permissions"] = permissions
    return user


def require_permission(form_key: str, requires_write: bool = False) -> Callable:
    def _checker(request: Request, current_user=Depends(get_current_user)):
        ui_permission = resolve_ui_permission(request.url.path, request.method)
        api_permission = resolve_api_permissions(
            request.url.path, request.method, request.query_params
        )
        if ui_permission:
            allowed = user_has_permission(current_user, *ui_permission)
        elif api_permission:
            keys, write = api_permission
            allowed = user_has_any_permission(current_user, keys, write)
        else:
            allowed = user_has_permission(current_user, form_key, requires_write)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permiso insuficiente",
            )
        return current_user

    return _checker


def require_api_screen_permission(
    request: Request,
    current_user=Depends(get_current_user_optional),
):
    if request.url.path.startswith("/api/tipo-cambio/sync-"):
        return current_user
    if request.url.path == "/api/system/logo" and request.method in {"GET", "HEAD"}:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No autenticado",
            )
        return current_user
    if request.url.path.startswith(
        (
            "/api/health",
            "/api/auth/",
        )
    ):
        return current_user
    permission = resolve_api_permissions(
        request.url.path,
        request.method,
        request.query_params,
    )
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Endpoint sin política de permisos",
        )
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
        )
    keys, requires_write = permission
    if not user_has_any_permission(current_user, keys, requires_write):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permiso insuficiente",
        )
    return current_user
