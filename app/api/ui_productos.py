from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.producto_service import listar_productos
from ..services.rubro_service import listar_rubros
from ..services.unidad_service import listar_unidades
from ..utils.health import db_status


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/productos", response_class=HTMLResponse)
async def ui_productos(
    request: Request,
    q: Optional[str] = Query(default=None),
    tipo: Optional[str] = Query(default=None),
    activo: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    # Parse activo igual que en API para evitar error con cadena vacía
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
            activo_val = None  # Ignorar valores inesperados en UI
    error = None
    productos = []
    unidades = []
    rubros = []
    try:
        productos = listar_productos(
            db, q=q, tipo=tipo, activo=activo_val, limit=limit, offset=0
        )
        unidades = listar_unidades(db)
        rubros = listar_rubros(db, only_active=True)

        um_map = {u["id"]: (u["codigo"], u["nombre"]) for u in unidades}
        for p in productos:
            codigo_um, nombre_um = um_map.get(p["unidad_medida_id"], ("?", ""))
            p["um_codigo"] = codigo_um
            p["um_nombre"] = nombre_um
    except SQLAlchemyError as ex:
        error = str(getattr(ex, "orig", ex))
    except ValueError as ex:
        error = str(ex)
    status = db_status(db)
    return templates.TemplateResponse(
        "productos/index.html",
        {
            "request": request,
            "q": q,
            "tipo": tipo,
            "activo": activo_val,  # pasar bool ya normalizado
            "limit": limit,
            "productos": productos,
            "unidades": unidades,
            "rubros": rubros,
            "error": error,
            "db_status": status,
        },
    )
