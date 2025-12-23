from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.utils.health import db_status

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    status = db_status(db)
    return templates.TemplateResponse(
        "auth/login.html",
        {
            "request": request,
            "db_status": status,
        },
    )


@router.get("/login_fragment", response_class=HTMLResponse)
async def login_fragment(request: Request):
    """Devuelve solo el fragmento del formulario de login para uso en modal/AJAX."""
    return templates.TemplateResponse(
        "auth/login_fragment.html",
        {"request": request},
    )


@router.get("/logout", response_class=HTMLResponse)
async def logout_page():
    resp = RedirectResponse(url="/ui/login", status_code=302)
    # Limpia la cookie del token
    resp.delete_cookie("access_token", path="/")
    return resp
