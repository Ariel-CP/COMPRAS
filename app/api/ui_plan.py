from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..db import get_db
from ..utils.health import db_status

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")


@router.get("/plan", response_class=HTMLResponse)
async def ui_plan(request: Request, db: Session = Depends(get_db)):
    """Vista principal de Plan de Producción Mensual (ABM moderno)."""
    status = db_status(db)
    return templates.TemplateResponse(
        "plan/plan_mensual.html",
        {"request": request, "db_status": status},
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
