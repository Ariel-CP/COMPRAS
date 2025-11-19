from datetime import date
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..db import get_db
from ..utils.health import db_status

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def ui_home(request: Request, db: Session = Depends(get_db)):
    status = db_status(db)
    hoy = date.today().isoformat()
    return templates.TemplateResponse(
        "home/index.html",
        {
            "request": request,
            "db_status": status,
            "hoy": hoy,
        },
    )
