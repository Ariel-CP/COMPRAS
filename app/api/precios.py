from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas.precio import PrecioCompraOut
from ..services.precio_service import listar_precios_compra


router = APIRouter()


@router.get("/historial", response_model=list[PrecioCompraOut])
def api_historial_precios(
    producto_id: Optional[int] = Query(
        default=None, description="ID de producto"
    ),
    q: Optional[str] = Query(
        default=None, description="Texto en producto o proveedor"
    ),
    proveedor: Optional[str] = Query(
        default=None, description="Código/Nombre proveedor"
    ),
    desde: Optional[date] = Query(default=None),
    hasta: Optional[date] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    try:
        return listar_precios_compra(
            db,
            producto_id=producto_id,
            q=q,
            proveedor=proveedor,
            desde=desde,
            hasta=hasta,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError as ex:
        raise HTTPException(
            status_code=500, detail=str(getattr(ex, "orig", ex))
        ) from ex
