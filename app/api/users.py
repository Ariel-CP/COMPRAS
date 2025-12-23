from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps_auth import require_permission
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserOut])
def list_users(
    q: Optional[str] = Query(default=None),
    activo: Optional[str] = Query(default=None, description="true|false"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("admin_usuarios", False)),
):
    try:
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
                    detail="Valor 'activo' inválido, use true/false",
                )
        return user_service.list_users(
            db, q=q, activo=activo_val, limit=limit, offset=offset
        )
    except SQLAlchemyError as ex:
        raise HTTPException(
            status_code=500, detail=str(getattr(ex, "orig", ex))
        ) from ex


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("admin_usuarios", False)),
):
    try:
        user = user_service.get_user(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        return user
    except SQLAlchemyError as ex:
        raise HTTPException(
            status_code=500, detail=str(getattr(ex, "orig", ex))
        ) from ex


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("admin_usuarios", True)),
):
    try:
        existing = user_service.list_users(db, q=payload.email, limit=1)
        if existing and existing[0]["email"].lower() == payload.email.lower():
            raise HTTPException(status_code=400, detail="Email ya registrado")
        return user_service.create_user(
            db,
            email=payload.email,
            nombre=payload.nombre,
            password=payload.password,
            activo=payload.activo,
            roles=payload.roles,
        )
    except SQLAlchemyError as ex:
        raise HTTPException(
            status_code=500, detail=str(getattr(ex, "orig", ex))
        ) from ex


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("admin_usuarios", True)),
):
    try:
        user = user_service.get_user(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        updated = user_service.update_user(
            db,
            user_id=user_id,
            nombre=payload.nombre if payload.nombre is not None else user["nombre"],
            password=payload.password,
            activo=payload.activo if payload.activo is not None else user["activo"],
            roles=payload.roles if payload.roles is not None else user.get("roles", []),
        )
        return updated
    except SQLAlchemyError as ex:
        raise HTTPException(
            status_code=500, detail=str(getattr(ex, "orig", ex))
        ) from ex


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("admin_usuarios", True)),
):
    try:
        user = user_service.get_user(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        user_service.deactivate_user(db, user_id)
    except SQLAlchemyError as ex:
        raise HTTPException(
            status_code=500, detail=str(getattr(ex, "orig", ex))
        ) from ex
