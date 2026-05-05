from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse

from .core.version import APP_VERSION
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import (
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.deps_auth import get_current_user

from .api import (
    ui_admin,
    ui_auth,
    ui_evaluaciones,
    ui_home,
    ui_informes,
    ui_mbom,
    ui_plan,
    ui_precios,
    ui_proveedores,
    ui_productos,
    ui_stock,
    ui_tipo_cambio,
)
from .api.router import api_router
from .services.backup_scheduler import (
    start_backup_scheduler,
    stop_backup_scheduler,
)
from .services.recepcion_scheduler import (
    start_recepcion_scheduler,
    stop_recepcion_scheduler,
)


def _patch_template_response_compat() -> None:
    """Mantiene compatibilidad con la firma vieja de TemplateResponse.

    En Starlette nuevas versiones esperan `request=` explícito. El proyecto
    usa la forma histórica `TemplateResponse(name, context)` en múltiples
    vistas UI.
    """

    original = Jinja2Templates.TemplateResponse
    if getattr(original, "_compras_compat", False):
        return

    def compat_template_response(self, *args, **kwargs):
        if len(args) >= 2 and isinstance(args[0], str) and isinstance(args[1], dict):
            name = args[0]
            context = args[1]
            # Inyectar app_version en todos los contextos de template
            context.setdefault("app_version", APP_VERSION)
            request = kwargs.pop("request", None) or context.get("request")
            if request is not None:
                return original(
                    self,
                    request=request,
                    name=name,
                    context=context,
                    **kwargs,
                )
        return original(self, *args, **kwargs)

    setattr(compat_template_response, "_compras_compat", True)
    setattr(Jinja2Templates, "TemplateResponse", compat_template_response)


_patch_template_response_compat()


@asynccontextmanager
async def app_lifespan(_application: FastAPI):
    start_backup_scheduler()
    start_recepcion_scheduler()
    try:
        yield
    finally:
        stop_recepcion_scheduler()
        stop_backup_scheduler()


def create_app() -> FastAPI:
    # Usar un nombre diferente evita el warning de redefinición
    application = FastAPI(
        title="Compras Backend",
        version=APP_VERSION,
        lifespan=app_lifespan,
        docs_url=None,  # deshabilitamos para inyectar CSS personalizado
        redoc_url="/redoc",
        swagger_ui_parameters={
            "docExpansion": "list",
            "defaultModelsExpandDepth": 0,
            "defaultModelExpandDepth": 1,
            "displayOperationId": True,
            "syntaxHighlight": {"activated": True, "theme": "tomorrow-night"},
        },
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(api_router, prefix="/api")
    # UI routers directamente en /ui
    application.include_router(ui_home.router, prefix="/ui")
    application.include_router(ui_auth.router, prefix="/ui")

    from .api import ui_rubros, ui_sessions

    # Proteger routers UI (exigir login). ui_auth (login) y ui_home quedan públicas.
    deps = [Depends(get_current_user)]
    application.include_router(ui_admin.router, prefix="/ui", dependencies=deps)
    application.include_router(ui_sessions.router, prefix="/ui", dependencies=deps)
    application.include_router(ui_evaluaciones.router, prefix="/ui", dependencies=deps)
    application.include_router(ui_plan.router, prefix="/ui", dependencies=deps)
    application.include_router(ui_stock.router, prefix="/ui", dependencies=deps)
    application.include_router(ui_productos.router, prefix="/ui", dependencies=deps)
    application.include_router(ui_mbom.router, prefix="/ui", dependencies=deps)
    application.include_router(ui_informes.router, prefix="/ui", dependencies=deps)
    application.include_router(ui_precios.router, prefix="/ui", dependencies=deps)
    application.include_router(ui_proveedores.router, prefix="/ui", dependencies=deps)
    application.include_router(ui_tipo_cambio.router, prefix="/ui", dependencies=deps)
    application.include_router(ui_rubros.router, prefix="/ui", dependencies=deps)

    # Static files
    application.mount(
        "/static",
        StaticFiles(directory="app/static"),
        name="static",
    )

    @application.middleware("http")
    async def ui_login_middleware(request, call_next):
        """Middleware que bloquea acceso a `/ui/*` si no hay sesión.

        Excluye rutas públicas (`/ui/login`, `/ui/logout`, `/static`, `/api`).
        - Para GET/HEAD: redirige a `/ui/login?next=...`.
        - Para otras methods: devuelve JSON 401.
        """
        request.state.current_user = None
        path = request.url.path or ""
        if path.startswith("/ui"):
            # exclusiones públicas
            if (
                path.startswith("/ui/login")
                or path.startswith("/ui/logout")
                or path.startswith("/static")
                or path.startswith("/api")
            ):
                return await call_next(request)

            # comprobar token/usuario
            from fastapi.responses import JSONResponse, RedirectResponse

            from app.db import SessionLocal

            db = SessionLocal()
            try:
                from app.api.deps_auth import decode_current_user_from_cookie

                user = decode_current_user_from_cookie(request, db)
            finally:
                db.close()

            # adjuntar usuario al request para plantillas
            request.state.current_user = user

            if not user:
                if request.method in ("GET", "HEAD"):
                    return RedirectResponse(url=f"/ui/login?next={request.url.path}", status_code=302)
                return JSONResponse(status_code=401, content={"detail": "No autenticado"})

        return await call_next(request)

    @application.get("/favicon.ico", include_in_schema=False)
    def favicon_ico_redirect():
        return RedirectResponse(url="/static/favicon.svg", status_code=307)

    @application.get("/")
    def root():
        return RedirectResponse(url="/ui/login", status_code=302)

    @application.get("/health")
    def health():
        return {"status": "healthy"}

    @application.get("/docs", include_in_schema=False)
    def custom_swagger_ui():
        return get_swagger_ui_html(
            openapi_url=application.openapi_url,
            title="Compras API Docs",
            oauth2_redirect_url="/docs/oauth2-redirect",
            swagger_js_url=(
                "https://cdn.jsdelivr.net/npm/"
                "swagger-ui-dist@5/swagger-ui-bundle.js"
            ),
            swagger_css_url="/static/css/swagger-theme.css",
        )

    @application.get("/docs/oauth2-redirect", include_in_schema=False)
    def swagger_ui_redirect():
        return get_swagger_ui_oauth2_redirect_html()

    return application


app = create_app()
