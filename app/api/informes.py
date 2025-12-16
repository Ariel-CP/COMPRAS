"""Endpoints para informes y reportes analíticos."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.informe_costos_service import costos_por_productos, listar_costos_pt

router = APIRouter(prefix="/informes", tags=["informes"])


class InformeCostosComparacionIn(BaseModel):
    """Payload para solicitar la comparación de costos de productos terminados."""

    producto_ids: List[int] = Field(default_factory=list, description="IDs de productos a comparar")
    codigos: List[str] = Field(default_factory=list, description="Códigos de productos a comparar")

    def elementos(self) -> int:
        return len(self.producto_ids) + len(self.codigos)


@router.get("/costos-pt")
def obtener_costos_pt(
    q: Optional[str] = Query(default=None, description="Filtro por código o nombre"),
    limit: int = Query(default=50, ge=1, le=200, description="Cantidad máxima de registros a devolver"),
    offset: int = Query(default=0, ge=0, description="Desplazamiento para paginado"),
    db: Session = Depends(get_db),
) -> dict:
    """Devuelve el listado de productos terminados con su costo agregado."""

    items = listar_costos_pt(db, q=q, limit=limit, offset=offset)
    return {"items": items, "count": len(items)}


@router.post("/costos-pt/comparar")
def comparar_costos_pt(
    payload: InformeCostosComparacionIn,
    db: Session = Depends(get_db),
) -> dict:
    """Devuelve la comparación de costos para los productos solicitados."""

    if payload.elementos() == 0:
        raise HTTPException(status_code=400, detail="Debe indicar al menos un producto para comparar")

    items = costos_por_productos(
        db,
        producto_ids=payload.producto_ids,
        codigos=payload.codigos,
    )
    return {"items": items, "count": len(items)}
