from datetime import date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, condecimal


StockCantidad = condecimal(ge=0, max_digits=18, decimal_places=6)


# Modelo para importar stock mensual
class StockMensualImport(BaseModel):
    periodo: str  # formato YYYY-MM
    codigo_producto: str
    cantidad: float
    unidad_medida: str
    fecha_stock: Optional[date]

    model_config = ConfigDict(from_attributes=True)


# Modelo de salida para listar stock mensual
class StockMensualOut(BaseModel):
    id: int
    periodo: str
    codigo_producto: str
    cantidad: float
    unidad_medida: str
    fecha_stock: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class StockItemOut(BaseModel):
    id: int
    anio: int
    mes: int
    producto_codigo: str
    detalle: str
    stock_disponible: StockCantidad  # type: ignore
    fecha_corte: str
    origen: str


class StockImportResult(BaseModel):
    insertados: int
    actualizados: int
    rechazados: int
    errores: List[str] = Field(default_factory=list)
