from datetime import date
from typing import Optional

from fastapi import APIRouter, Request, Query, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from ..db import get_db
from ..services.stock_import_service import (
    listar_stock_periodo,
    resumen_stock_periodo,
)
from ..utils.health import db_status

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")


@router.get("/stock", response_class=HTMLResponse)
async def ui_stock(
    request: Request,
    anio: int = Query(default=date.today().year),
    mes: int = Query(default=date.today().month, ge=1, le=12),
    q: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    error = None
    stock = []
    resumen = {"items": 0, "total_stock": 0}
    try:
        stock = listar_stock_periodo(db, anio, mes, q)
        resumen = resumen_stock_periodo(db, anio, mes)
    except SQLAlchemyError as ex:
        error = str(getattr(ex, "orig", ex))
    except ValueError as ex:
        error = str(ex)
    status = db_status(db)
    return templates.TemplateResponse(
        "stock/index.html",
        {
            "request": request,
            "anio": anio,
            "mes": mes,
            "q": q,
            "fecha_corte": date.today().isoformat(),
            "stock": stock,
            "resumen": resumen,
            "error": error,
            "db_status": status,
        },
    )
