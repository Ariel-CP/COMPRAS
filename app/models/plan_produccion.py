<<<<<<< HEAD
from pydantic import BaseModel, ConfigDict, Field, field_validator

=======
from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional
>>>>>>> e0cbf5e965dc7e466c7150be8761ee1658919b54

class PlanProduccionBase(BaseModel):
    producto_id: int
    mes: int
    anio: int
    cantidad: float = Field(..., gt=0)

    @field_validator('mes')
    @classmethod
    def mes_valido(cls, v):
        if not (1 <= v <= 12):
            raise ValueError('El mes debe estar entre 1 y 12')
        return v

    @field_validator('anio')
    @classmethod
    def anio_valido(cls, v):
        if v < 2000 or v > 2100:
            raise ValueError('Año fuera de rango')
        return v


class PlanProduccionCreate(PlanProduccionBase):
    pass


class PlanProduccionUpdate(PlanProduccionBase):
    pass


class PlanProduccionOut(PlanProduccionBase):
    id: int
    producto_codigo: str
    producto_nombre: str

    model_config = ConfigDict(from_attributes=True)
