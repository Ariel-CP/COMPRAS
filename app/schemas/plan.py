from typing import List, Optional
from pydantic import BaseModel, Field, condecimal


class PlanItemIn(BaseModel):
    producto_codigo: str = Field(..., min_length=1, max_length=64)
    cantidad: condecimal(ge=0, max_digits=18, decimal_places=6)  # type: ignore


class PlanItemOut(BaseModel):
    id: int
    anio: int
    mes: int
    producto_codigo: str
    cantidad_planificada: condecimal(ge=0, max_digits=18, decimal_places=6)  # type: ignore


class PlanUpsertIn(BaseModel):
    items: List[PlanItemIn]


class PlanUpsertResult(BaseModel):
    insertados: int
    actualizados: int
    rechazados: int
    errores: List[str] = []
