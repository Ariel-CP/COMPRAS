from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps_auth import require_permission
from app.schemas.proveedor import ProveedorCreate, ProveedorOut, ProveedorUpdate
from app.services.proveedor_service import (
    actualizar_proveedor,
    crear_proveedor,
    eliminar_proveedor,
    listar_proveedores,
    obtener_proveedor,
)
from app.services.proveedor_import_service import importar_proveedores_desde_csv

router = APIRouter(prefix="/proveedores", tags=["proveedores"])


@router.get("/", response_model=list[ProveedorOut])
def api_listar_proveedores(
    q: Optional[str] = Query(default=None),
    activo: Optional[str] = Query(default=None, description="true|false"),
    limit: int = Query(default=200, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _current_user: dict = Depends(require_permission("proveedores", False)),
):
    activo_val: Optional[bool]
    if activo is None or activo == "":
        activo_val = None
    else:
        value = activo.lower()
        if value in {"true", "1", "si", "sí"}:
            activo_val = True
        elif value in {"false", "0", "no"}:
            activo_val = False
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Valor 'activo' invalido. Use true/false",
            )

    try:
        return listar_proveedores(db, q=q, activo=activo_val, limit=limit, offset=offset)
    except SQLAlchemyError as ex:
        raise HTTPException(status_code=500, detail=str(getattr(ex, "orig", ex))) from ex


@router.get("/{proveedor_id}", response_model=ProveedorOut)
def api_obtener_proveedor(
    proveedor_id: int,
    db: Session = Depends(get_db),
    _current_user: dict = Depends(require_permission("proveedores", False)),
):
    try:
        proveedor = obtener_proveedor(db, proveedor_id)
        if not proveedor:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado")
        return proveedor
    except SQLAlchemyError as ex:
        raise HTTPException(status_code=500, detail=str(getattr(ex, "orig", ex))) from ex


@router.post("/", response_model=ProveedorOut, status_code=status.HTTP_201_CREATED)
def api_crear_proveedor(
    payload: ProveedorCreate,
    db: Session = Depends(get_db),
    _current_user: dict = Depends(require_permission("proveedores", True)),
):
    try:
        return crear_proveedor(db, payload.model_dump())
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    except SQLAlchemyError as ex:
        raise HTTPException(status_code=500, detail=str(getattr(ex, "orig", ex))) from ex


@router.put("/{proveedor_id}", response_model=ProveedorOut)
def api_actualizar_proveedor(
    proveedor_id: int,
    payload: ProveedorUpdate,
    db: Session = Depends(get_db),
    _current_user: dict = Depends(require_permission("proveedores", True)),
):
    try:
        updated = actualizar_proveedor(
            db,
            proveedor_id,
            payload.model_dump(exclude_unset=True),
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado")
        return updated
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    except SQLAlchemyError as ex:
        raise HTTPException(status_code=500, detail=str(getattr(ex, "orig", ex))) from ex


@router.delete("/{proveedor_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_eliminar_proveedor(
    proveedor_id: int,
    db: Session = Depends(get_db),
    _current_user: dict = Depends(require_permission("proveedores", True)),
):
    try:
        deleted = eliminar_proveedor(db, proveedor_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado")
        return None
    except SQLAlchemyError as ex:
        msg = str(getattr(ex, "orig", ex))
        if "foreign key constraint fails" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede eliminar: el proveedor esta referenciado",
            ) from ex
        raise HTTPException(status_code=500, detail=msg) from ex


@router.post("/import", status_code=status.HTTP_200_OK)
async def api_importar_proveedores(
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    _current_user: dict = Depends(require_permission("proveedores", True)),
):
    """
    Importa proveedores desde archivo CSV (formato ERP Flexxus).
    
    Columnas esperadas (cualquier orden, con alias detectados):
    - Código / Code
    - Razón Social / Nombre / Name
    - C.U.I.T. / CUIT (opcional)
    - E-Mail / Email (opcional)
    - Teléfono / Telefono / Phone (opcional)
    - Dirección / Direccion / Address (opcional)
    - Localidad / Ciudad / City (opcional)
    - Provincia / Estado / State (opcional)
    
    Delimitadores soportados: ; , \\t
    Encoding: UTF-8 (con fallback a latin-1)
    
    Returns:
        {
            "status": "success" | "error",
            "insertados": int,
            "actualizados": int,
            "rechazados": int,
            "errores": [{"fila": int, "codigo": str, "mensaje": str}]
        }
    """
    if not archivo.filename or not archivo.filename.endswith(('.csv', '.CSV')):
        raise HTTPException(
            status_code=400,
            detail="Solo se aceptan archivos CSV",
        )
    
    try:
        contenido = await archivo.read()
        
        if not contenido:
            raise HTTPException(
                status_code=400,
                detail="Archivo vacío",
            )
        
        resultado = importar_proveedores_desde_csv(db, contenido)
        
        return resultado
        
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando archivo: {str(ex)[:200]}",
        ) from ex
