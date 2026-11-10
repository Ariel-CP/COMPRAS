from ipaddress import ip_address

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.deps_auth import require_permission
from app.schemas.ai_settings import AISettingsIn, ConnectionTestIn
from app.services.ai_settings_service import (
    AISettingsError,
    get_ai_settings,
    save_ai_settings,
)

from app.services.ai_connection_test_service import test_openai_connection

router = APIRouter(prefix="/system/settings/ia", tags=["system"])


def _check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(
            403, "La configuración debe guardarse desde el mismo sitio."
        )


@router.get("")
def read_ai_settings(
    response: Response,
    _current_user: dict = Depends(require_permission("ui_admin_settings", False)),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        return get_ai_settings()
    except AISettingsError as exc:
        raise HTTPException(503, str(exc)) from None


@router.post("")
def write_ai_settings(
    payload: AISettingsIn,
    request: Request,
    response: Response,
    _current_user: dict = Depends(require_permission("ui_admin_settings", True)),
):
    _check_origin(request)
    if payload.api_key and payload.api_key.get_secret_value().strip():
        try:
            loopback = (
                request.client is not None
                and ip_address(request.client.host).is_loopback
            )
        except ValueError:
            loopback = False
        if request.url.scheme != "https" and not loopback:
            raise HTTPException(
                400, "Ingresá la clave mediante HTTPS o desde localhost en el servidor."
            )
    response.headers["Cache-Control"] = "no-store"
    try:
        return save_ai_settings(payload, int(_current_user.get("id") or 0))
    except AISettingsError as exc:
        raise HTTPException(400, str(exc)) from None


@router.post("/probar")
def connection_test(
    payload: ConnectionTestIn,
    request: Request,
    response: Response,
    _current_user: dict = Depends(require_permission("ui_admin_settings", True)),
):
    _check_origin(request)
    response.headers["Cache-Control"] = "no-store"
    try:
        return test_openai_connection(int(_current_user.get("id") or 0))
    except AISettingsError as exc:
        raise HTTPException(400, str(exc)) from None
