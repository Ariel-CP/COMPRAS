"""
API para gestión de operaciones (catálogo maestro).
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..services import operacion_service


router = APIRouter(tags=["operaciones"])


class OperacionCreate(BaseModel):
    codigo: str = Field(..., min_length=1, max_length=32)
    nombre: str = Field(..., min_length=1, max_length=128)
    centro_trabajo: str = Field(..., min_length=1, max_length=64)
    tiempo_estandar_minutos: float = Field(default=0, ge=0)
    costo_hora: float = Field(default=0, ge=0)
    moneda: str = Field(default="ARS", pattern="^(ARS|USD|USD_MAY|EUR)$")


class OperacionUpdate(BaseModel):
    codigo: Optional[str] = Field(None, min_length=1, max_length=32)
    nombre: Optional[str] = Field(None, min_length=1, max_length=128)
    centro_trabajo: Optional[str] = Field(None, min_length=1, max_length=64)
    tiempo_estandar_minutos: Optional[float] = Field(None, ge=0)
    costo_hora: Optional[float] = Field(None, ge=0)
    moneda: Optional[str] = Field(None, pattern="^(ARS|USD|USD_MAY|EUR)$")


@router.get("/operaciones/")
def listar_operaciones_endpoint(
    q: Optional[str] = Query(None, description="Búsqueda por código, nombre o centro"),
    centro_trabajo: Optional[str] = Query(None, description="Filtrar por centro"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Lista operaciones con filtros opcionales."""
    return operacion_service.listar_operaciones(
        db=db,
        q=q,
        centro_trabajo=centro_trabajo,
        limit=limit,
        offset=offset,
    )


@router.get("/operaciones/{operacion_id}")
def obtener_operacion_endpoint(
    operacion_id: int,
    db: Session = Depends(get_db),
):
    """Obtiene una operación por ID."""
    operacion = operacion_service.obtener_operacion(db, operacion_id)
    if not operacion:
        raise HTTPException(status_code=404, detail="Operación no encontrada")
    return operacion


@router.post("/operaciones/", status_code=201)
def crear_operacion_endpoint(
    data: OperacionCreate,
    db: Session = Depends(get_db),
):
    """Crea una nueva operación."""
    try:
        return operacion_service.crear_operacion(
            db=db,
            codigo=data.codigo,
            nombre=data.nombre,
            centro_trabajo=data.centro_trabajo,
            tiempo_estandar_minutos=data.tiempo_estandar_minutos,
            costo_hora=data.costo_hora,
            moneda=data.moneda,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Error al crear operación: {str(e)}"
        )


@router.put("/operaciones/{operacion_id}")
def actualizar_operacion_endpoint(
    operacion_id: int,
    data: OperacionUpdate,
    db: Session = Depends(get_db),
):
    """Actualiza una operación existente."""
    operacion = operacion_service.obtener_operacion(db, operacion_id)
    if not operacion:
        raise HTTPException(status_code=404, detail="Operación no encontrada")
    
    try:
        return operacion_service.actualizar_operacion(
            db=db,
            operacion_id=operacion_id,
            codigo=data.codigo,
            nombre=data.nombre,
            centro_trabajo=data.centro_trabajo,
            tiempo_estandar_minutos=data.tiempo_estandar_minutos,
            costo_hora=data.costo_hora,
            moneda=data.moneda,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Error al actualizar operación: {str(e)}"
        )


@router.delete("/operaciones/{operacion_id}", status_code=204)
def eliminar_operacion_endpoint(
    operacion_id: int,
    db: Session = Depends(get_db),
):
    """Elimina una operación."""
    try:
        if not operacion_service.eliminar_operacion(db, operacion_id):
            raise HTTPException(
                status_code=404,
                detail="Operación no encontrada"
            )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Error al eliminar operación: {str(e)}"
        )
