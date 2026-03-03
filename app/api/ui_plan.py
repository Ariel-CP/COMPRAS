import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.deps_auth import require_permission
from app.services.plan_produccion_service import listar_periodos_cargados

from ..db import get_db
from ..utils.health import db_status

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")
_env_name = os.environ.get("ENV", os.environ.get("ENVIRONMENT", "")).lower()
if _env_name != "production":
    templates.env.auto_reload = True
    templates.env.cache = {}


@router.get("/plan", response_class=HTMLResponse)
async def ui_plan(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("plan", False)),
):
    """Vista principal de Plan de Producción Mensual (ABM moderno)."""
    status = db_status(db)
    periodos = listar_periodos_cargados(db)
    return templates.TemplateResponse(
        "plan/plan_mensual.html",
        {
            "request": request,
            "db_status": status,
            "current_user": current_user,
            "periodos": periodos,
        },
    )


@router.get("/plan-mensual", response_class=HTMLResponse)
async def ui_plan_mensual(request: Request):
    return templates.TemplateResponse(
        "plan/plan_mensual.html",
        {"request": request},
    )


@router.get("/plan-variaciones", response_class=HTMLResponse)
async def ui_plan_variaciones(request: Request):
    return templates.TemplateResponse(
        "plan/plan_variaciones.html",
        {"request": request},
    )


@router.get("/plan-requerimientos", response_class=HTMLResponse)
async def ui_plan_requerimientos(request: Request):
    return templates.TemplateResponse(
        "plan/plan_requerimientos.html",
        {"request": request},
    )
