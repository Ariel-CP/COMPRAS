from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.plan_produccion import PlanProduccionCreate, PlanProduccionUpdate, PlanProduccionOut
from app.services.plan_produccion_service import listar_planes, crear_plan, actualizar_plan, eliminar_plan
from app.api.deps import get_db

router = APIRouter(prefix="/plan-produccion-mensual", tags=["plan-produccion-mensual"])

@router.get("/", response_model=dict)
def listar(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    mes: Optional[int] = None,
    anio: Optional[int] = None,
    producto_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    items, total = listar_planes(db, limit=limit, offset=offset, mes=mes, anio=anio, producto_id=producto_id)
    return {"items": items, "total": total}

@router.post("/", response_model=int)
def crear(plan: PlanProduccionCreate, db: Session = Depends(get_db)):
    try:
        return crear_plan(db, plan)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{plan_id}")
def editar(plan_id: int, plan: PlanProduccionUpdate, db: Session = Depends(get_db)):
    try:
        actualizar_plan(db, plan_id, plan)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{plan_id}")
def borrar(plan_id: int, db: Session = Depends(get_db)):
    eliminar_plan(db, plan_id)
    return {"ok": True}
