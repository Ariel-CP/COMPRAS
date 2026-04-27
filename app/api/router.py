from fastapi import APIRouter

from .auth import router as auth_router
from .backups import router as backups_router
from .health import router as health_router
from .system_api import router as system_router
from .informes import router as informes_router
from .mbom_api import router as mbom_router
from .operacion_api import router as operacion_router
from .plan import router as plan_router
from .plan_produccion import router as plan_produccion_router
from .precios import router as precios_router
from .proveedores import router as proveedores_router
from .productos import router as productos_router
from .roles import router as roles_router
from .rubros import router as rubros_router
from .stock import router as stock_router
from .tipo_cambio import router as tipo_cambio_router
from .unidades import router as unidades_router
from .users import router as users_router

api_router = APIRouter()

api_router.include_router(plan_router, prefix="/plan", tags=["plan"])
api_router.include_router(stock_router, prefix="/stock", tags=["stock"])
api_router.include_router(health_router, prefix="/health")
api_router.include_router(backups_router, prefix="/backups", tags=["backups"])
api_router.include_router(productos_router, prefix="/productos", tags=["productos"])
api_router.include_router(unidades_router, prefix="/unidades", tags=["unidades"])
api_router.include_router(mbom_router, tags=["mbom"])
api_router.include_router(informes_router)
api_router.include_router(plan_produccion_router)
api_router.include_router(operacion_router)
api_router.include_router(precios_router, prefix="/precios", tags=["precios"])
api_router.include_router(proveedores_router)
api_router.include_router(tipo_cambio_router, prefix="/tipo-cambio", tags=["tipo-cambio"])

api_router.include_router(rubros_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)
api_router.include_router(system_router)
