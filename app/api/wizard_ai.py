from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.ai_settings import _check_origin
from app.api.deps_auth import require_permission
from app.schemas.wizard_ai import WizardChatIn
from app.services.ai_settings_service import AISettingsError
from app.services.wizard_ai_service import chat_status, converse

router = APIRouter(
    prefix="/plan-produccion-mensual/asistente-oc/ia/conversacion", tags=["wizard-ia"]
)


@router.get("/estado")
def status(
    response: Response, user=Depends(require_permission("ui_plan_asistente_oc", False))
):
    response.headers["Cache-Control"] = "no-store"
    try:
        return chat_status()
    except AISettingsError as exc:
        raise HTTPException(503, str(exc)) from None


@router.post("")
def chat(
    payload: WizardChatIn,
    request: Request,
    response: Response,
    user=Depends(require_permission("ui_plan_asistente_oc", False)),
):
    _check_origin(request)
    response.headers["Cache-Control"] = "no-store"
    try:
        return converse(payload, int(user.get("id") or 0))
    except AISettingsError as exc:
        raise HTTPException(400, str(exc)) from None
