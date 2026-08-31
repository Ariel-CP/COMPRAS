from datetime import date
from typing import Optional, List, Literal
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, ConfigDict


class TipoCambioBase(BaseModel):
    fecha: date = Field(..., description="Fecha del tipo de cambio")
    moneda: Literal["ARS", "USD", "USD_MAY", "EUR"] = Field(
        ..., description="Moneda (ARS, USD, USD_MAY, EUR)"
    )
    tipo: Literal["COMPRA", "VENTA", "PROMEDIO"] = Field(
        "PROMEDIO", description="Tipo de tasa: COMPRA, VENTA, PROMEDIO"
    )
    tasa: float = Field(..., description="Valor de la tasa en pesos", gt=0)
    origen: Literal["ERP_FLEXXUS", "MANUAL", "OTRO"] = Field(
        "MANUAL", description="Origen del dato (MANUAL, ERP_FLEXXUS, OTRO)"
    )
    notas: Optional[str] = Field(None, description="Notas opcionales")

    @field_validator("tasa", mode="before")
    @classmethod
    def convert_decimal(cls, v):
        if isinstance(v, Decimal):
            return float(v)
        return v


class TipoCambioCreate(TipoCambioBase):
    pass


class TipoCambioUpdate(BaseModel):
    tasa: Optional[float] = Field(None, gt=0)
    origen: Optional[str] = None
    notas: Optional[str] = None

    @field_validator("tasa", mode="before")
    @classmethod
    def convert_decimal(cls, v):
        if v is None:
            return v
        if isinstance(v, Decimal):
            return float(v)
        return v


class TipoCambioOut(TipoCambioBase):
    id: int
    fecha_creacion: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class TipoCambioFiltro(BaseModel):
    moneda: Optional[str] = None
    tipo: Optional[str] = None
    desde: Optional[date] = None
    hasta: Optional[date] = None


class BulkImportResult(BaseModel):
    insertados: int
    actualizados: int
    errores: int
    detalle_errores: List[str] = []


class TipoCambioSyncResponse(BaseModel):
    insertados: int
    actualizados: int
    procesados: int
    desde: date
    hasta: date


class TipoCambioSyncHistoricoResponse(BaseModel):
    """Respuesta de sincronización histórica de BCRA."""
    fecha_desde: date
    fecha_hasta: date
    recibidos: int
    insertados: int
    actualizados: int
    sin_cambios: int
    errores: int
