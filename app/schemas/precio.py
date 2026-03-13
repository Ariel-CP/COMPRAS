from datetime import date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class PrecioCompraIn(BaseModel):
    producto_id: int
    proveedor_codigo: str
    proveedor_nombre: Optional[str] = None
    fecha_precio: date
    precio_unitario: float
    moneda: str = "ARS"
    referencia_doc: Optional[str] = None
    notas: Optional[str] = None


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

    model_config = ConfigDict(from_attributes=True)


class PrecioImportResult(BaseModel):
    insertados: int
    actualizados: int
    rechazados: int
    errores: List[str] = []
