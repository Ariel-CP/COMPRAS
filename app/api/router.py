from fastapi import APIRouter

from . import (
        plan,
        stock,
        health,
        productos,
        unidades,
        mbom_api,
        informes,
        operacion_api,
        precios,
        tipo_cambio,
        plan_produccion,
        rubros,
<<<<<<< HEAD
        auth,
        users,
        roles,
=======
>>>>>>> e0cbf5e965dc7e466c7150be8761ee1658919b54
)

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
        informes.router
)
api_router.include_router(
        plan_produccion.router
)
api_router.include_router(
        operacion_api.router
)
api_router.include_router(
        precios.router, prefix="/precios", tags=["precios"]
)
api_router.include_router(
        tipo_cambio.router, prefix="/tipo-cambio", tags=["tipo-cambio"]
)

<<<<<<< HEAD
api_router.include_router(rubros.router, tags=["rubros"])
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(roles.router)
=======
api_router.include_router(rubros.router, prefix="/rubros", tags=["rubros"])
>>>>>>> e0cbf5e965dc7e466c7150be8761ee1658919b54
