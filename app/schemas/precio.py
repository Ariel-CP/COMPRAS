from typing import Optional
from datetime import date
from pydantic import BaseModel


class PrecioCompraOut(BaseModel):
    id: int
    producto_id: int
    producto_codigo: str
    producto_nombre: str
    proveedor_codigo: str
    proveedor_nombre: Optional[str] = None
    fecha_precio: date
    precio_unitario: float
    moneda: str
    origen: str
    referencia_doc: Optional[str] = None
    notas: Optional[str] = None

    class Config:
        from_attributes = True
