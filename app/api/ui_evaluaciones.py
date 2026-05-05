from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.proveedor_service import listar_proveedores

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/evaluaciones", response_class=HTMLResponse)
async def ui_evaluaciones(request: Request, db: Session = Depends(get_db)):
    proveedores = listar_proveedores(db, activo=True, limit=2000, offset=0)
    anno_actual = date.today().year

    # Años con evaluaciones registradas (para el filtro)
    annos = list(range(anno_actual, anno_actual - 8, -1))

    return templates.TemplateResponse(
        "evaluaciones/index.html",
        {
            "request": request,
            "proveedores": proveedores,
            "anno_actual": anno_actual,
            "annos": annos,
        },
    )
