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


@router.get("/evaluaciones/ranking", response_class=HTMLResponse)
async def ui_evaluaciones_ranking(request: Request):
    hoy = date.today()
    desde_default = date(hoy.year, 1, 1)
    return templates.TemplateResponse(
        "evaluaciones/ranking.html",
        {
            "request": request,
            "desde_default": str(desde_default),
            "hasta_default": str(hoy),
        },
    )


@router.get("/evaluaciones/ranking-print", response_class=HTMLResponse)
async def ui_evaluaciones_ranking_print(
    request: Request,
    desde: str | None = None,
    hasta: str | None = None,
):
    hoy = date.today()
    desde_default = str(date(hoy.year, 1, 1))
    return templates.TemplateResponse(
        "evaluaciones/ranking_print.html",
        {
            "request": request,
            "desde_default": desde or desde_default,
            "hasta_default": hasta or str(hoy),
        },
    )


@router.get("/evaluaciones/evolucion", response_class=HTMLResponse)
async def ui_evaluaciones_evolucion(
    request: Request,
    db: Session = Depends(get_db),
    proveedor_id: int | None = None,
    desde: str | None = None,
    hasta: str | None = None,
):
    proveedores = listar_proveedores(db, activo=True, limit=2000, offset=0)
    hoy = date.today()
    desde_default = str(date(hoy.year, 1, 1))
    return templates.TemplateResponse(
        "evaluaciones/evolucion.html",
        {
            "request": request,
            "proveedores": proveedores,
            "proveedor_id_default": proveedor_id,
            "desde_default": desde or desde_default,
            "hasta_default": hasta or str(hoy),
        },
    )
