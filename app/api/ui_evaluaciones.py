from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps_auth import require_permission
from app.services.proveedor_service import listar_proveedores
from app.services.access_read_service import AccessReadError
from app.services.evaluacion_preview_service import obtener_vista_previa

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get(
    "/evaluaciones/vista-previa",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("ui_evaluaciones"))],
)
def ui_evaluaciones_vista_previa(
    request: Request,
    q: str = Query(default="", max_length=100),
    access_id: int | None = Query(default=None, ge=1),
):
    datos = None
    error = None
    try:
        datos = obtener_vista_previa(q=q, access_id=access_id)
    except (AccessReadError, FileNotFoundError):
        error = "No se pudo consultar Access. Verificá que el servidor tenga acceso a la unidad de red."
    return templates.TemplateResponse(
        "evaluaciones/vista_previa.html",
        {
            "request": request,
            "datos": datos,
            "error": error,
            "q": q,
            "access_id": access_id,
        },
        status_code=503 if error else 200,
    )


@router.get(
    "/evaluaciones",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("evaluaciones"))],
)
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


@router.get(
    "/evaluaciones/ranking",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("evaluaciones_ranking"))],
)
async def ui_evaluaciones_ranking(
    request: Request, desde: date | None = None, hasta: date | None = None,
):
    return templates.TemplateResponse(
        "evaluaciones/ranking.html",
        {
            "request": request,
            "desde_default": str(desde or date(2026, 1, 1)),
            "hasta_default": str(hasta or date(2026, 7, 31)),
        },
    )


@router.get(
    "/evaluaciones/ranking-print",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("evaluaciones_ranking_print"))],
)
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


@router.get(
    "/evaluaciones/evolucion",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("evaluaciones_evolucion"))],
)
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
