from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..db import get_db
from ..utils.health import db_status
templates = Jinja2Templates(directory="app/templates")
router = APIRouter()

# Ruta para formulario de stock mensual
@router.get("/stock", response_class=HTMLResponse)
def stock_mensual_form(request: Request, db: Session = Depends(get_db)):
    status = db_status(db)
    return templates.TemplateResponse("stock/stock_mensual.html", {"request": request, "db_status": status})
