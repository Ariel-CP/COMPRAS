from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.producto_service import listar_productos
from ..utils.health import db_status


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/informes/costos-pt", response_class=HTMLResponse)
async def ui_informe_costos_pt(
    request: Request,
    db: Session = Depends(get_db),
):
    """Renderiza el informe de costos de productos terminados."""

    productos_pt = listar_productos(
        db,
        q=None,
        tipo="PT",
        activo=True,
        limit=500,
        offset=0,
    )
    status = db_status(db)
    return templates.TemplateResponse(
        "informes/costos_pt.html",
        {
            "request": request,
            "productos": productos_pt,
            "db_status": status,
        },
    )
