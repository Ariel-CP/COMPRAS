from typing import Optional
from datetime import date
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.tipo_cambio_service import obtener_resumen_ultimas_tasas
from ..utils.health import db_status

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/tipo-cambio", response_class=HTMLResponse)
async def ui_tipo_cambio(
    request: Request,
    moneda: Optional[str] = Query(default=None),
    tipo: Optional[str] = Query(default=None),
    desde: Optional[date] = Query(default=None),
    hasta: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
):
    status = db_status(db)
    ultimas_tasas = obtener_resumen_ultimas_tasas(db)
    return templates.TemplateResponse(
        "tipo_cambio/historial.html",
        {
            "request": request,
            "moneda": moneda,
            "tipo": tipo,
            "desde": desde.isoformat() if desde else "",
            "hasta": hasta.isoformat() if hasta else "",
            "db_status": status,
            "ultimas_tasas": ultimas_tasas,
        },
    )
