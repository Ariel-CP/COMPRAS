from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


class CriterioDetalleIn(BaseModel):
    categoria: str = Field(..., pattern=r"^(CALIDAD|SERVICIO|EMBALAJE)$")
    criterio_codigo: str = Field(..., max_length=64)
    criterio_nombre: Optional[str] = Field(default=None, max_length=150)
    puntaje: Optional[float] = Field(default=None, ge=0, le=100)
    comentario: Optional[str] = Field(default=None, max_length=500)


class CriterioDetalleOut(CriterioDetalleIn):
    id: int


class EvaluacionCreate(BaseModel):
    proveedor_id: int
    anno: int = Field(..., ge=2000, le=2099)
    periodo: int = Field(default=0, ge=0, le=3,
                         description="0=Anual, 1=1er Cuatri, 2=2do Cuatri, 3=3er Cuatri")
    tipo_evaluacion: str = Field(default="ANUAL", pattern=r"^(ANUAL|CUATRIMESTRAL)$")

    puntaje_calidad: Optional[float] = Field(default=None, ge=0, le=100)
    puntaje_servicio: Optional[float] = Field(default=None, ge=0, le=100)
    puntaje_embalaje: Optional[float] = Field(default=None, ge=0, le=100)

    evaluador_nombre: Optional[str] = Field(default=None, max_length=128)
    sector_evaluador: Optional[str] = Field(default=None, max_length=100)
    fecha_evaluacion: Optional[date] = None
    proxima_evaluacion: Optional[date] = None
    observaciones: Optional[str] = None
    referencias: Optional[str] = None

    criterios: List[CriterioDetalleIn] = Field(default_factory=list)


class EvaluacionOut(BaseModel):
    id: int
    proveedor_id: int
    proveedor_nombre: Optional[str] = None
    proveedor_codigo: Optional[str] = None
    anno: int
    periodo: int
    tipo_evaluacion: str
    puntaje_calidad: Optional[float] = None
    puntaje_servicio: Optional[float] = None
    puntaje_embalaje: Optional[float] = None
    puntaje_total: Optional[float] = None
    resultado: Optional[str] = None
    evaluador_nombre: Optional[str] = None
    sector_evaluador: Optional[str] = None
    fecha_evaluacion: Optional[str] = None
    proxima_evaluacion: Optional[str] = None
    observaciones: Optional[str] = None
    referencias: Optional[str] = None
    usuario_id: Optional[int] = None
    fecha_creacion: Optional[str] = None
    fecha_actualizacion: Optional[str] = None
    criterios: List[CriterioDetalleOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class EvaluacionListItem(BaseModel):
    id: int
    proveedor_id: int
    proveedor_nombre: Optional[str] = None
    proveedor_codigo: Optional[str] = None
    anno: int
    periodo: int
    tipo_evaluacion: str
    puntaje_total: Optional[float] = None
    resultado: Optional[str] = None
    evaluador_nombre: Optional[str] = None
    fecha_evaluacion: Optional[str] = None
    proxima_evaluacion: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
