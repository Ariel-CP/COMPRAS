from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import date
from decimal import Decimal

# Modelo para importar stock mensual
class StockMensualImport(BaseModel):
    periodo: str  # formato YYYY-MM
    codigo_producto: str
    cantidad: float
    unidad_medida: str
    fecha_stock: Optional[date]

    @field_validator('cantidad')
    def cantidad_to_float(cls, v):
        return float(v)

    @field_validator('fecha_stock')
    def fecha_to_str(cls, v):
        if v is None:
            return None
        return v.isoformat() if isinstance(v, date) else v

    class Config:
        from_attributes = True

# Modelo de salida para listar stock mensual
class StockMensualOut(BaseModel):
    id: int
    periodo: str
    codigo_producto: str
    cantidad: float
    unidad_medida: str
    fecha_stock: Optional[str]

    class Config:
        from_attributes = True
from typing import List
from pydantic import BaseModel, condecimal


StockCantidad = condecimal(ge=0, max_digits=18, decimal_places=6)


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
    errores: List[str] = []
