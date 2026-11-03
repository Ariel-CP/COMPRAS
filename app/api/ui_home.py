from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.deps_auth import get_current_user_optional

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")

FORM_OPTIONS = (
    ("plan", "/ui/plan", "Plan de Producción", "Cargar y editar cantidades por período."),
    ("plan", "/ui/plan-asistente-oc", "Wizard OC", "Preparar órdenes de compra desde el plan."),
    ("stock", "/ui/stock", "Stock Mensual", "Consultar e importar datos de stock."),
    ("productos", "/ui/productos", "Artículos", "Consultar y gestionar artículos."),
    ("mbom", "/ui/mbom", "Estructura", "Consultar estructuras de materiales."),
    ("informes", "/ui/informes/costos-pt", "Costos PT", "Consultar costos de productos terminados."),
    ("precios", "/ui/precios", "Precios", "Consultar y gestionar precios."),
    ("proveedores", "/ui/proveedores", "Proveedores", "Consultar y gestionar proveedores."),
    ("recepcion", "/ui/recepcion", "Recepción", "Registrar ingresos y controles de materiales."),
    ("proveedores", "/ui/evaluaciones", "Evaluaciones", "Consultar evaluaciones de proveedores."),
    ("tipo_cambio", "/ui/tipo-cambio", "Tipo de cambio", "Consultar cotizaciones y su historial."),
    ("admin_backups", "/ui/admin/backups", "Backups", "Administrar copias de seguridad."),
    ("admin_usuarios", "/ui/admin/usuarios", "Usuarios", "Administrar usuarios del sistema."),
    ("admin_roles", "/ui/admin/permisos", "Permisos", "Configurar permisos por rol."),
    ("admin_roles", "/ui/admin/roles", "Roles", "Administrar roles del sistema."),
    ("admin_sistema", "/ui/admin/logo", "Logo", "Configurar el logo del sistema."),
    ("admin_sistema", "/ui/admin/settings", "Configuración del sistema", "Consultar configuración del sistema."),
)


def get_available_forms(current_user: dict) -> list[dict[str, str]]:
    """Devuelve los formularios visibles para los permisos del usuario."""
    permissions = current_user.get("permissions", {})
    available_forms = []
    for permission_key, destination, name, description in FORM_OPTIONS:
        permission = permissions.get(permission_key, (False, False)) if permission_key else (True, False)
        if permission and permission[0]:
            available_forms.append(
                {"url": destination, "name": name, "description": description}
            )
    return available_forms


@router.get("/", response_class=HTMLResponse)
async def ui_home(
    request: Request,
    current_user=Depends(get_current_user_optional),
):
    # Si no hay sesión, redirigir al login (mostrar login al iniciar)
    if not current_user:
        return RedirectResponse(url="/ui/login?next=/ui", status_code=302)

    return templates.TemplateResponse(
        "home/index.html",
        {
            "request": request,
            "current_user": current_user,
            "form_options": get_available_forms(current_user),
        },
    )
