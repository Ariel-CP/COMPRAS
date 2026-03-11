from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.mbom_service import listar_producto_padre_ids_con_estructura_con_datos
from ..services.producto_service import listar_productos
from ..services.unidad_service import listar_unidades
from ..utils.health import db_status


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/mbom", response_class=HTMLResponse)
async def ui_mbom(
    request: Request,
    producto_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    # Combinar productos PT y WIP activos para el selector
    productos_pt = listar_productos(
        db, q=None, tipo="PT", activo=True, limit=500, offset=0
    )
    productos_wip = listar_productos(
        db, q=None, tipo="WIP", activo=True, limit=500, offset=0
    )
    productos = sorted(
        [*productos_pt, *productos_wip], key=lambda p: p.get("codigo") or ""
    )
    ids_con_estructura = set(
        listar_producto_padre_ids_con_estructura_con_datos(
            db, [int(p["id"]) for p in productos if p.get("id") is not None]
        )
    )
    unidades = listar_unidades(db)
    um_map = {u["id"]: u["codigo"] for u in unidades}
    status = db_status(db)
    return templates.TemplateResponse(
        "mbom/estructura.html",
        {
            "request": request,
            "productos": productos,
            "unidades": unidades,
            "um_map": um_map,
            "producto_id": producto_id,
            "db_status": status,
            "ids_con_estructura": ids_con_estructura,
        },
    )
