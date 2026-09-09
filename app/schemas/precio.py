from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


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
    importacion_id: Optional[int] = None
    insertados: int
    actualizados: int
    rechazados: int
    errores: List[str] = Field(default_factory=list)


class PrecioImportLoteOut(BaseModel):
    id: int
    archivo_nombre: Optional[str] = None
    archivo_hash: Optional[str] = None
    formato: str
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    total_registros: int
    insertados: int
    actualizados: int
    rechazados: int
    estado: str
    mensaje_error: Optional[str] = None
    usuario_id: Optional[int] = None
    usuario_nombre: Optional[str] = None
    usuario_email: Optional[str] = None


class PrecioVariacionOut(BaseModel):
    modo: str
    producto_id: int
    producto_codigo: str
    producto_nombre: str
    proveedor_codigo: str
    proveedor_nombre: Optional[str] = None
    moneda: str
    fecha_base: date
    fecha_nueva: date
    precio_base: float
    precio_nuevo: float
    variacion_abs: float
    variacion_pct: Optional[float] = None
