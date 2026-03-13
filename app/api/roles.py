from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps_auth import require_permission
from app.schemas.role import (
    PermissionIn,
    RoleCreate,
    RoleOut,
    RolePerms,
    RoleUpdate,
)
from app.services import user_service

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("/", response_model=List[RoleOut])
def list_roles(
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("admin_roles", False)),
):
    try:
        return user_service.list_roles(db)
    except SQLAlchemyError as ex:
        raise HTTPException(
            status_code=500, detail=str(getattr(ex, "orig", ex))
        ) from ex


@router.post("/", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("admin_roles", True)),
):
    try:
        return user_service.create_role(db, payload.nombre, payload.descripcion)
    except SQLAlchemyError as ex:
        raise HTTPException(
            status_code=400, detail=str(getattr(ex, "orig", ex))
        ) from ex


@router.put("/{rol_id}", response_model=RoleOut)
def update_role(
    rol_id: int,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("admin_roles", True)),
):
    try:
        role = user_service.get_role(db, rol_id)
        if not role:
            raise HTTPException(status_code=404, detail="Rol no encontrado")
        updated = user_service.update_role(
            db, rol_id, nombre=payload.nombre or role["nombre"], descripcion=payload.descripcion
        )
        return updated
    except SQLAlchemyError as ex:
        raise HTTPException(
            status_code=400, detail=str(getattr(ex, "orig", ex))
        ) from ex


@router.delete("/{rol_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    rol_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("admin_roles", True)),
):
    try:
        role = user_service.get_role(db, rol_id)
        if not role:
            raise HTTPException(status_code=404, detail="Rol no encontrado")
        user_service.delete_role(db, rol_id)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    except SQLAlchemyError as ex:
        raise HTTPException(
            status_code=400, detail=str(getattr(ex, "orig", ex))
        ) from ex


@router.get("/{rol_id}/perms", response_model=RolePerms)
def get_role_perms(
    rol_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("admin_roles", False)),
):
    try:
        role = user_service.get_role(db, rol_id)
        if not role:
            raise HTTPException(status_code=404, detail="Rol no encontrado")
        perms = user_service.get_role_perms(db, rol_id)
        return {"rol": role, "permisos": perms}
    except SQLAlchemyError as ex:
        raise HTTPException(
            status_code=500, detail=str(getattr(ex, "orig", ex))
        ) from ex


@router.put("/{rol_id}/perms", response_model=RolePerms)
def set_role_perms(
    rol_id: int,
    payload: List[PermissionIn],
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("admin_roles", True)),
):
    try:
        role = user_service.get_role(db, rol_id)
        if not role:
            raise HTTPException(status_code=404, detail="Rol no encontrado")
        perms = user_service.set_role_perms(db, rol_id, [p.dict() for p in payload])
        return {"rol": role, "permisos": perms}
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    except SQLAlchemyError as ex:
        raise HTTPException(
            status_code=400, detail=str(getattr(ex, "orig", ex))
        ) from ex
