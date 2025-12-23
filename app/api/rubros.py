from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.rubro import RubroCreate, RubroOut, RubroUpdate
from app.services.rubro_service import listar_rubros, crear_rubro, actualizar_rubro, eliminar_rubro, existe_rubro_unico


router = APIRouter(prefix="/rubros", tags=["rubros"])


@router.get("/", response_model=List[RubroOut])
def list_rubros(
    only_active: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """Lista todos los rubros (opcionalmente solo activos)."""
    return [RubroOut(**r) for r in listar_rubros(db, only_active=only_active)]


@router.post("/", response_model=RubroOut, status_code=status.HTTP_201_CREATED)
def create_rubro(rubro_in: RubroCreate, db: Session = Depends(get_db)):
    """Crea un nuevo rubro."""
    if existe_rubro_unico(db, rubro_in.nombre):
        raise HTTPException(status_code=409, detail="El nombre de rubro ya existe")
    try:
        rubro = crear_rubro(db, rubro_in.nombre)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El nombre de rubro ya existe")
    # Convertir a dict para evitar pasar Column
    return RubroOut.model_validate({
        "id": rubro.id,
        "nombre": rubro.nombre,
        "activo": rubro.activo,
        "creado_en": rubro.creado_en,
        "actualizado_en": rubro.actualizado_en,
    })


@router.put("/{rubro_id}", response_model=RubroOut)
def update_rubro(
    rubro_id: int, rubro_in: RubroUpdate, db: Session = Depends(get_db)
):
    """Actualiza un rubro existente."""
    if rubro_in.nombre is None:
        raise HTTPException(status_code=400, detail="Nombre requerido")
    if existe_rubro_unico(db, rubro_in.nombre, exclude_id=rubro_id):
        raise HTTPException(status_code=409, detail="El nombre de rubro ya existe")
    nombre = rubro_in.nombre
    try:
        rubro = actualizar_rubro(db, rubro_id, nombre)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El nombre de rubro ya existe")
    if not rubro:
        raise HTTPException(status_code=404, detail="Rubro no encontrado")
    return RubroOut.model_validate({
        "id": rubro.id,
        "nombre": rubro.nombre,
        "activo": rubro.activo,
        "creado_en": rubro.creado_en,
        "actualizado_en": rubro.actualizado_en,
    })


@router.delete("/{rubro_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rubro(rubro_id: int, db: Session = Depends(get_db)):
    """Elimina un rubro."""
    ok = eliminar_rubro(db, rubro_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Rubro no encontrado")
