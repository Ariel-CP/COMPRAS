from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api.deps_auth import require_permission

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/recepcion", response_class=HTMLResponse)
def ui_recepcion(
    request: Request,
    current_user: dict = Depends(require_permission("recepcion", False)),
):
    return templates.TemplateResponse(
        "recepcion/formulario.html",
        {
            "request": request,
            "current_user": current_user,
            "hoy": date.today().isoformat(),
        },
    )


@router.get("/recepcion/controles", response_class=HTMLResponse)
def ui_recepcion_controles(
    request: Request,
    current_user: dict = Depends(require_permission("recepcion", False)),
):
    return templates.TemplateResponse(
        "recepcion/controles.html",
        {"request": request, "current_user": current_user},
    )


@router.get("/recepcion/calidad", response_class=HTMLResponse)
def ui_recepcion_calidad(
    request: Request,
    current_user: dict = Depends(require_permission("recepcion", False)),
):
    return templates.TemplateResponse(
        "recepcion/calidad.html",
        {"request": request, "current_user": current_user},
    )


@router.get("/recepcion/calidad/linea/{linea_id}", response_class=HTMLResponse)
def ui_recepcion_calidad_linea(
    linea_id: int,
    request: Request,
    current_user: dict = Depends(require_permission("recepcion", False)),
):
    return templates.TemplateResponse(
        "recepcion/calidad_material.html",
        {"request": request, "current_user": current_user, "linea_id": linea_id},
    )


@router.get("/recepcion/historial-access", response_class=HTMLResponse)
def ui_recepcion_historial_access(
    request: Request,
    current_user: dict = Depends(require_permission("recepcion", False)),
):
    return templates.TemplateResponse(
        "recepcion/historial_access.html",
        {"request": request, "current_user": current_user},
    )
