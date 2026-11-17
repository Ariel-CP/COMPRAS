from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ControlRechazado(BaseModel):
    id: int
    fecha: date


class ProveedorPuntaje(BaseModel):
    codigo: str
    nombre: str
    periodo: str | None = None
    recepciones: int
    rechazos: int = 0
    controles_rechazados: list[ControlRechazado] = Field(default_factory=list)
    calidad: Decimal
    entrega: Decimal
    certificado: Decimal
    total: Decimal
    resultado: str
    sin_fecha_oc: int
    sin_plan: int
    sin_plazo: int
    identidad_por_nombre: int


class ResumenRanking(BaseModel):
    controles_periodo: int
    controles_evaluados: int
    controles_excluidos: int
    proveedores: int
    resultados: dict[str, int]
    sin_fecha_oc: int
    sin_plan: int
    sin_plazo: int
    identidad_por_nombre: int
    exclusiones_por_motivo: dict[str, int]


class RankingPowerBIOut(BaseModel):
    desde: date
    hasta: date
    metodologia: str
    calculado_en: datetime
    resumen: ResumenRanking
    proveedores: list[ProveedorPuntaje]
    mejores_20: list[ProveedorPuntaje]
    peores_20: list[ProveedorPuntaje]


class HistorialPowerBIOut(BaseModel):
    codigo: str
    proveedor: ProveedorPuntaje | None
    desde: date | None
    hasta: date
    agrupacion: str
    metodologia: str
    calculado_en: datetime
    serie: list[ProveedorPuntaje]
