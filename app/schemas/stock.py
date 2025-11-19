from typing import List
from pydantic import BaseModel, Field, condecimal


class StockItemOut(BaseModel):
    id: int
    anio: int
    mes: int
    producto_codigo: str
    stock_disponible: condecimal(ge=0, max_digits=18, decimal_places=6)  # type: ignore
    fecha_corte: str
    origen: str


class StockImportResult(BaseModel):
    insertados: int
    actualizados: int
    rechazados: int
    errores: List[str] = []
