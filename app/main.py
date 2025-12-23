from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import (
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)

from .api.router import api_router
from .api import (
    ui_plan,
    ui_stock,
    ui_home,
    ui_productos,
    ui_mbom,
    ui_informes,
    ui_precios,
    ui_tipo_cambio,
    ui_auth,
    ui_admin,
)
from app.api.deps_auth import get_current_user


def create_app() -> FastAPI:
    # Usar un nombre diferente evita el warning de redefinición
    application = FastAPI(
        title="Compras Backend",
        version="0.1.0",
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
    from app.api import ui_sessions
    # Proteger routers UI (exigir login). ui_auth (login) y ui_home quedan públicas.
    application.include_router(ui_admin.router, prefix="/ui", dependencies=[Depends(get_current_user)])
    application.include_router(ui_sessions.router, prefix="/ui", dependencies=[Depends(get_current_user)])
    application.include_router(ui_plan.router, prefix="/ui", dependencies=[Depends(get_current_user)])
    application.include_router(ui_stock.router, prefix="/ui", dependencies=[Depends(get_current_user)])
    application.include_router(ui_productos.router, prefix="/ui", dependencies=[Depends(get_current_user)])
    application.include_router(ui_mbom.router, prefix="/ui", dependencies=[Depends(get_current_user)])
    application.include_router(ui_informes.router, prefix="/ui", dependencies=[Depends(get_current_user)])
    application.include_router(ui_precios.router, prefix="/ui", dependencies=[Depends(get_current_user)])
    application.include_router(ui_tipo_cambio.router, prefix="/ui", dependencies=[Depends(get_current_user)])
    # Nuevo router para rubros UI
    from app.api import ui_rubros
    application.include_router(ui_rubros.router, prefix="/ui")

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
            from app.db import SessionLocal
            from fastapi.responses import RedirectResponse, JSONResponse

            db = SessionLocal()
            try:
                from app.api.deps_auth import decode_current_user_from_cookie

                user = decode_current_user_from_cookie(request, db)
            finally:
                db.close()

            # adjuntar usuario al request para plantillas
            try:
                request.state.current_user = user
            except Exception:
                pass

            if not user:
                if request.method in ("GET", "HEAD"):
                    return RedirectResponse(url=f"/ui/login?next={request.url.path}", status_code=302)
                return JSONResponse(status_code=401, content={"detail": "No autenticado"})

        return await call_next(request)

    @application.get("/")
    def root():
        return {"name": "compras", "status": "ok"}

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
