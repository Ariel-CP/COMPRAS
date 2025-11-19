from datetime import date

from fastapi import APIRouter, Request, Query, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from ..db import get_db
from ..services.plan_service import get_plan_periodo
from ..utils.health import db_status

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")


@router.get("/plan", response_class=HTMLResponse)
async def ui_plan(
    request: Request,
    anio: int = Query(default=date.today().year),
    mes: int = Query(default=date.today().month, ge=1, le=12),
    db: Session = Depends(get_db),
):
    error = None
    plan = []
    try:
        plan = get_plan_periodo(db, anio, mes)
    except SQLAlchemyError as ex:
        # extraer mensaje original de DB si existe
        error = str(getattr(ex, "orig", ex))
    except ValueError as ex:
        error = str(ex)
    status = db_status(db)
    return templates.TemplateResponse(
        "plan/index.html",
        {
            "request": request,
            "anio": anio,
            "mes": mes,
            "plan": plan,
            "error": error,
            "db_status": status,
        },
    )
