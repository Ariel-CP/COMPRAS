from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.proveedor_service import listar_proveedores

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/proveedores", response_class=HTMLResponse)
async def ui_proveedores(
    request: Request,
    q: Optional[str] = Query(default=None),
    activo: Optional[str] = Query(default=None),
    limit: int = Query(default=2000, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    activo_val: Optional[bool]
    if activo is None or activo == "":
        activo_val = None
    else:
        v = activo.lower()
        if v in {"true", "1", "si", "sí"}:
            activo_val = True
        elif v in {"false", "0", "no"}:
            activo_val = False
        else:
            activo_val = None

    proveedores = []
    error = None
    try:
        proveedores = listar_proveedores(
            db,
            q=q,
            activo=activo_val,
            limit=limit,
            offset=0,
        )
    except SQLAlchemyError as ex:
        error = str(getattr(ex, "orig", ex))

    return templates.TemplateResponse(
        "proveedores/index.html",
        {
            "request": request,
            "q": q,
            "activo": activo_val,
            "limit": limit,
            "proveedores": proveedores,
            "error": error,
        },
    )
