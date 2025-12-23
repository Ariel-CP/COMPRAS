from datetime import date
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..db import get_db
from ..utils.health import db_status
from app.api.deps_auth import get_current_user_optional

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def ui_home(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    # Si no hay sesión, redirigir al login (mostrar login al iniciar)
    if not current_user:
        return RedirectResponse(url="/ui/login?next=/ui", status_code=302)

    status = db_status(db)
    hoy = date.today().isoformat()
    return templates.TemplateResponse(
        "home/index.html",
        {
            "request": request,
            "db_status": status,
            "hoy": hoy,
            "current_user": current_user,
        },
    )
