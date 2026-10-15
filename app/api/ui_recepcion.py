from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.api.deps_auth import require_permission

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/recepcion", response_class=HTMLResponse)
def ui_recepcion(
    request: Request,
    current_user: dict = Depends(require_permission("recepcion", False)),
):
    return templates.TemplateResponse(
        "recepcion/index.html",
        {
            "request": request,
            "current_user": current_user,
            "hoy": date.today().isoformat(),
        },
    )
