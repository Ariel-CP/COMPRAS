from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas.precio import (
    PrecioCompraIn,
    PrecioCompraOut,
    PrecioImportLoteOut,
    PrecioImportResult,
    PrecioVariacionOut,
)
from ..services.precio_service import (
    crear_precio_compra_manual,
    exportar_variaciones_csv,
    exportar_variaciones_xlsx,
    generar_template_precios,
    importar_precios_desde_archivo,
    listar_importaciones_precios,
    listar_precios_compra,
    listar_variaciones_precios,
)
from .deps_auth import require_permission

router = APIRouter()


def _safe_user_id(user: Optional[dict]) -> Optional[int]:
    if not user:
        return None
    raw_id = user.get("id")
    try:
        value = int(raw_id)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


@router.post("/manual", response_model=PrecioCompraOut)
def api_crear_precio_manual(
    payload: PrecioCompraIn,
    db: Session = Depends(get_db),
    _current_user=Depends(require_permission("precios", True)),
):
    try:
        return crear_precio_compra_manual(
            db,
            producto_id=payload.producto_id,
            proveedor_codigo=payload.proveedor_codigo,
            proveedor_nombre=payload.proveedor_nombre,
            fecha_precio=payload.fecha_precio,
            precio_unitario=payload.precio_unitario,
            moneda=payload.moneda,
            referencia_doc=payload.referencia_doc,
            notas=payload.notas,
            current_user_id=_safe_user_id(_current_user),
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    except SQLAlchemyError as ex:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=str(getattr(ex, "orig", ex))
        ) from ex


@router.get("/historial", response_model=list[PrecioCompraOut])
def api_historial_precios(
    producto_id: Optional[int] = Query(default=None, description="ID de producto"),
    q: Optional[str] = Query(default=None, description="Texto en producto o proveedor"),
    proveedor: Optional[str] = Query(
        default=None, description="Código/Nombre proveedor"
    ),
    desde: Optional[date] = Query(default=None),
    hasta: Optional[date] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _current_user=Depends(require_permission("precios", False)),
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


@router.get("/template-xlsx")
def descargar_template_precios():
    stream = generar_template_precios()
    headers = {
        "Content-Disposition": (
            "attachment; filename=template_precios_historial.xlsx"
        )
    }
    return StreamingResponse(
        stream,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers=headers,
    )


@router.post("/import", response_model=PrecioImportResult)
def importar_precios(
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    _current_user=Depends(require_permission("precios", True)),
):
    if not archivo.filename:
        raise HTTPException(status_code=400, detail="Archivo requerido")
    return importar_precios_desde_archivo(
        db,
        archivo,
        current_user_id=_safe_user_id(_current_user),
    )


@router.get("/importaciones", response_model=list[PrecioImportLoteOut])
def api_listar_importaciones(
    desde: Optional[date] = Query(default=None),
    hasta: Optional[date] = Query(default=None),
    estado: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _current_user=Depends(require_permission("precios", False)),
):
    try:
        return listar_importaciones_precios(
            db,
            desde=desde,
            hasta=hasta,
            estado=estado,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError as ex:
        raise HTTPException(
            status_code=500, detail=str(getattr(ex, "orig", ex))
        ) from ex


@router.get("/variaciones", response_model=list[PrecioVariacionOut])
def api_variaciones_precios(
    modo: str = Query(default="ultima_vs_anterior"),
    producto_id: Optional[int] = Query(default=None),
    proveedor: Optional[str] = Query(default=None),
    desde: Optional[date] = Query(default=None),
    hasta: Optional[date] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _current_user=Depends(require_permission("precios", False)),
):
    try:
        return listar_variaciones_precios(
            db,
            modo=modo,
            producto_id=producto_id,
            proveedor=proveedor,
            desde=desde,
            hasta=hasta,
            limit=limit,
            offset=offset,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    except SQLAlchemyError as ex:
        raise HTTPException(
            status_code=500, detail=str(getattr(ex, "orig", ex))
        ) from ex


@router.get("/variaciones/export")
def api_exportar_variaciones(
    formato: str = Query(default="csv"),
    modo: str = Query(default="ultima_vs_anterior"),
    producto_id: Optional[int] = Query(default=None),
    proveedor: Optional[str] = Query(default=None),
    desde: Optional[date] = Query(default=None),
    hasta: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
    _current_user=Depends(require_permission("precios", False)),
):
    try:
        rows = listar_variaciones_precios(
            db,
            modo=modo,
            producto_id=producto_id,
            proveedor=proveedor,
            desde=desde,
            hasta=hasta,
            limit=10000,
            offset=0,
        )
        formato_norm = (formato or "csv").lower().strip()
        if formato_norm == "xlsx":
            stream = exportar_variaciones_xlsx(rows)
            media_type = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            filename = f"variaciones_precios_{modo}.xlsx"
        elif formato_norm == "csv":
            stream = exportar_variaciones_csv(rows)
            media_type = "text/csv; charset=utf-8"
            filename = f"variaciones_precios_{modo}.csv"
        else:
            raise HTTPException(status_code=400, detail="Formato inválido")

        return StreamingResponse(
            stream,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            },
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    except SQLAlchemyError as ex:
        raise HTTPException(
            status_code=500, detail=str(getattr(ex, "orig", ex))
        ) from ex
