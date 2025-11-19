from typing import Literal
from pydantic import BaseModel, Field


TipoProducto = Literal["PT", "WIP", "MP", "EMB", "SERV", "HERR"]


class ProductoBase(BaseModel):
    codigo: str = Field(min_length=1, max_length=64)
    nombre: str = Field(min_length=1, max_length=128)
    tipo_producto: TipoProducto = Field(default="MP")
    unidad_medida_id: int = Field(gt=0)
    activo: bool = True


class ProductoIn(ProductoBase):
    pass


class ProductoOut(ProductoBase):
    id: int
