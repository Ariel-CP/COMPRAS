from fastapi import APIRouter

from . import plan, stock, health, productos, unidades, mbom_api, precios

api_router = APIRouter()

api_router.include_router(plan.router, prefix="/plan", tags=["plan"])
api_router.include_router(stock.router, prefix="/stock", tags=["stock"])
api_router.include_router(health.router, prefix="/health")
api_router.include_router(
        productos.router, prefix="/productos", tags=["productos"]
)
api_router.include_router(
        unidades.router, prefix="/unidades", tags=["unidades"]
)
api_router.include_router(
        mbom_api.router, tags=["mbom"]
)
api_router.include_router(
        precios.router, prefix="/precios", tags=["precios"]
)
