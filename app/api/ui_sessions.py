from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/sesiones", response_class=HTMLResponse)
async def sesiones_page(request: Request):
    """Página UI para que el usuario vea y revoque sus sesiones activas."""
    current_user = getattr(request.state, "current_user", None)
    return templates.TemplateResponse(
        "auth/sessions.html",
        {"request": request, "current_user": current_user},
    )
