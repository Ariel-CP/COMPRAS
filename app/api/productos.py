from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas.producto import ProductoIn, ProductoOut
from ..services.producto_service import (
    listar_productos,
    get_producto,
    crear_producto,
    actualizar_producto,
)


router = APIRouter()


@router.get("/", response_model=list[ProductoOut])
def api_listar_productos(
    q: Optional[str] = Query(default=None),
    tipo: Optional[str] = Query(default=None),
    activo: Optional[str] = Query(default=None, description="true|false"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    # Normalizar activo: '', None -> None; true/1 -> True; false/0 -> False
    activo_val: Optional[bool]
    if activo is None or activo == "":
        activo_val = None
    else:
        val = activo.lower()
        if val in {"true", "1", "si", "sí"}:
            activo_val = True
        elif val in {"false", "0", "no"}:
            activo_val = False
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Valor 'activo' inválido. Use true/false",
            )
    try:
        return listar_productos(
            db,
            q=q,
            tipo=tipo,
            activo=activo_val,
            limit=limit,
            offset=offset,
        )
    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(ex)
        ) from ex
    except SQLAlchemyError as ex:
        raise HTTPException(
            status_code=500, detail=str(getattr(ex, "orig", ex))
        ) from ex


@router.get("/{prod_id}", response_model=ProductoOut)
def api_get_producto(prod_id: int, db: Session = Depends(get_db)):
    try:
        prod = get_producto(db, prod_id)
        if not prod:
            raise HTTPException(
                status_code=404, detail="Producto no encontrado"
            )
        return prod
    except SQLAlchemyError as ex:
        raise HTTPException(
            status_code=500, detail=str(getattr(ex, "orig", ex))
        ) from ex


@router.post(
    "/",
    response_model=ProductoOut,
    status_code=status.HTTP_201_CREATED,
)
def api_crear_producto(payload: ProductoIn, db: Session = Depends(get_db)):
    try:
        return crear_producto(
            db,
            codigo=payload.codigo,
            nombre=payload.nombre,
            tipo_producto=payload.tipo_producto,
            unidad_medida_id=payload.unidad_medida_id,
            activo=payload.activo,
        )
    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(ex)
        ) from ex
    except SQLAlchemyError as ex:
        raise HTTPException(
            status_code=500, detail=str(getattr(ex, "orig", ex))
        ) from ex


@router.put("/{prod_id}", response_model=ProductoOut)
def api_actualizar_producto(
    prod_id: int,
    payload: ProductoIn,
    db: Session = Depends(get_db),
):
    try:
        return actualizar_producto(
            db,
            prod_id=prod_id,
            codigo=payload.codigo,
            nombre=payload.nombre,
            tipo_producto=payload.tipo_producto,
            unidad_medida_id=payload.unidad_medida_id,
            activo=payload.activo,
        )
    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(ex)
        ) from ex
    except SQLAlchemyError as ex:
        raise HTTPException(
            status_code=500, detail=str(getattr(ex, "orig", ex))
        ) from ex
