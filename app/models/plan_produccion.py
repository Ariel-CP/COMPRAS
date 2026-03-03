from pydantic import BaseModel, ConfigDict, Field, field_validator


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
