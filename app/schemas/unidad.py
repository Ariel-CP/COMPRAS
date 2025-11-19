from pydantic import BaseModel


class UnidadMedidaOut(BaseModel):
    id: int
    codigo: str
    nombre: str
