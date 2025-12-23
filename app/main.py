from fastapi import FastAPI
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
)


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
    application.include_router(ui_plan.router, prefix="/ui")
    application.include_router(ui_stock.router, prefix="/ui")
    application.include_router(ui_productos.router, prefix="/ui")
    application.include_router(ui_mbom.router, prefix="/ui")
    application.include_router(ui_informes.router, prefix="/ui")
    application.include_router(ui_precios.router, prefix="/ui")
    application.include_router(ui_tipo_cambio.router, prefix="/ui")
    # Nuevo router para rubros UI
    from app.api import ui_rubros
    application.include_router(ui_rubros.router, prefix="/ui")

    # Static files
    application.mount(
        "/static",
        StaticFiles(directory="app/static"),
        name="static",
    )

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
