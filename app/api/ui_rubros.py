from fastapi import APIRouter, Request, Form, status, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.services.rubro_service import (
    listar_rubros, crear_rubro, obtener_rubro_por_id, actualizar_rubro, eliminar_rubro, existe_rubro_unico
)
from fastapi.templating import Jinja2Templates
from fastapi import HTTPException

router = APIRouter()
# Las plantillas residen en app/templates
templates = Jinja2Templates(directory="app/templates")

@router.get("/rubros", response_class=HTMLResponse)
def rubros_list(request: Request, db: Session = Depends(get_db)):
    rubros = listar_rubros(db)
    return templates.TemplateResponse(
        "rubros/list.html",
        {"request": request, "rubros": rubros, "error": None, "nombre_inicial": None},
    )

@router.get("/rubros/nuevo", response_class=HTMLResponse)
def rubro_nuevo_form(request: Request):
    # Redirigimos al listado, donde está el formulario de alta.
    return RedirectResponse("/ui/rubros", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/rubros/nuevo", response_class=HTMLResponse)
def rubro_nuevo(request: Request, nombre: str = Form(...), db: Session = Depends(get_db)):
    if existe_rubro_unico(db, nombre):
        rubros = listar_rubros(db)
        return templates.TemplateResponse(
            "rubros/list.html",
            {
                "request": request,
                "rubros": rubros,
                "error": "El nombre ya existe.",
                "nombre_inicial": nombre,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    crear_rubro(db, nombre)
    return RedirectResponse("/ui/rubros", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/rubros/editar/{rubro_id}", response_class=HTMLResponse)
def rubro_editar_form(request: Request, rubro_id: int, db: Session = Depends(get_db)):
    rubro = obtener_rubro_por_id(db, rubro_id)
    if not rubro:
        raise HTTPException(status_code=404, detail="Rubro no encontrado")
    return templates.TemplateResponse("rubros/form.html", {"request": request, "rubro": rubro, "error": None})

@router.post("/rubros/editar/{rubro_id}", response_class=HTMLResponse)
def rubro_editar(request: Request, rubro_id: int, nombre: str = Form(...), db: Session = Depends(get_db)):
    if existe_rubro_unico(db, nombre, exclude_id=rubro_id):
        rubro = {"id": rubro_id, "nombre": nombre}
        return templates.TemplateResponse("rubros/form.html", {"request": request, "rubro": rubro, "error": "El nombre ya existe."})
    updated = actualizar_rubro(db, rubro_id, nombre)
    if not updated:
        raise HTTPException(status_code=404, detail="Rubro no encontrado")
    return RedirectResponse("/ui/rubros", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/rubros/eliminar/{rubro_id}", response_class=HTMLResponse)
def rubro_confirmar_eliminar(request: Request, rubro_id: int, db: Session = Depends(get_db)):
    rubro = obtener_rubro_por_id(db, rubro_id)
    if not rubro:
        raise HTTPException(status_code=404, detail="Rubro no encontrado")
    return templates.TemplateResponse("rubros/confirm_delete.html", {"request": request, "rubro": rubro})

@router.post("/rubros/eliminar/{rubro_id}")
def rubro_eliminar(request: Request, rubro_id: int, db: Session = Depends(get_db)):
    ok = eliminar_rubro(db, rubro_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Rubro no encontrado")
    return RedirectResponse("/ui/rubros", status_code=status.HTTP_303_SEE_OTHER)
