import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps_auth import require_permission
from app.services import user_service
from app.utils.health import db_status

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")
_env_name = os.environ.get("ENV", os.environ.get("ENVIRONMENT", "")).lower()
if _env_name != "production":
    templates.env.auto_reload = True
    templates.env.cache = {}


@router.get("/admin/usuarios", response_class=HTMLResponse)
async def admin_usuarios(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("admin_usuarios", False)),
):
    status = db_status(db)
    usuarios = user_service.list_users(db, limit=100, offset=0)
    usuarios = [
        {
            **u,
            "fecha_creacion": u.get("fecha_creacion"),
            "roles": u.get("roles", []),
        }
        for u in usuarios
    ]
    roles = user_service.list_roles(db)
    return templates.TemplateResponse(
        "admin/usuarios.html",
        {
            "request": request,
            "db_status": status,
            "usuarios": usuarios,
            "roles": roles,
            "current_user": current_user,
        },
    )


@router.get("/admin/permisos", response_class=HTMLResponse)
async def admin_permisos(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("admin_roles", False)),
):
    status = db_status(db)
    roles = user_service.list_roles(db)
    # permitir seleccionar rol vía query param ?role_id=NN
    role_id = request.query_params.get('role_id')
    initial_role = None
    if role_id:
        try:
            rid = int(role_id)
            initial_role = user_service.get_role(db, rid)
        except Exception:
            initial_role = None
    if not initial_role:
        initial_role = roles[0] if roles else None
    permisos = (
        user_service.get_role_perms(db, initial_role["id"]) if initial_role else []
    )
    return templates.TemplateResponse(
        "admin/permisos.html",
        {
            "request": request,
            "db_status": status,
            "roles": roles,
            "permisos": permisos,
            "selected_role": initial_role,
            "current_user": current_user,
        },
    )


@router.get("/admin/roles", response_class=HTMLResponse)
async def admin_roles(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("admin_roles", False)),
):
    status = db_status(db)
    roles = user_service.list_roles(db)
    return templates.TemplateResponse(
        "admin/roles.html",
        {"request": request, "db_status": status, "roles": roles, "current_user": current_user},
    )
