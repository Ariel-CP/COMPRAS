from typing import Optional
from datetime import date
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..db import get_db
from ..utils.health import db_status

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/precios", response_class=HTMLResponse)
async def ui_precios(
    request: Request,
    q: Optional[str] = Query(default=None),
    proveedor: Optional[str] = Query(default=None),
    desde: Optional[date] = Query(default=None),
    hasta: Optional[date] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    status = db_status(db)
    return templates.TemplateResponse(
        "precios/historial.html",
        {
            "request": request,
            "q": q,
            "proveedor": proveedor,
            "desde": desde.isoformat() if desde else "",
            "hasta": hasta.isoformat() if hasta else "",
            "limit": limit,
            "db_status": status,
        },
    )
