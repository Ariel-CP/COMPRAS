from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas.plan import PlanItemIn, PlanItemOut, PlanUpsertIn, PlanUpsertResult
from ..services.plan_service import (
    get_plan_periodo,
    upsert_plan_periodo,
    update_plan_item,
    delete_plan_periodo,
)

router = APIRouter()


@router.get("/{anio}/{mes}", response_model=List[PlanItemOut])
def listar_plan(anio: int, mes: int, db: Session = Depends(get_db)):
    if not (1 <= mes <= 12):
        raise HTTPException(status_code=400, detail="mes debe estar entre 1 y 12")
    return get_plan_periodo(db, anio, mes)


@router.post("/{anio}/{mes}", response_model=PlanUpsertResult)
def upsert_plan(
    anio: int,
    mes: int,
    payload: PlanUpsertIn,
    sobrescribir: bool = Query(False, description="Si true, borra y re-inserta el periodo"),
    db: Session = Depends(get_db),
):
    if not (1 <= mes <= 12):
        raise HTTPException(status_code=400, detail="mes debe estar entre 1 y 12")
    return upsert_plan_periodo(db, anio, mes, payload.items, sobrescribir)


@router.put("/{item_id}", response_model=PlanItemOut)
def actualizar_item(item_id: int, body: PlanItemIn, db: Session = Depends(get_db)):
    return update_plan_item(db, item_id, body)


@router.delete("/{anio}/{mes}")
def borrar_periodo(anio: int, mes: int, confirmar: bool = Query(False), db: Session = Depends(get_db)):
    if not confirmar:
        raise HTTPException(status_code=400, detail="Confirmar=true requerido para borrar el periodo")
    delete_plan_periodo(db, anio, mes)
    return {"status": "ok"}
