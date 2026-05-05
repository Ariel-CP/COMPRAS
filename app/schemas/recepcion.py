"""
Schemas Pydantic para endpoints de recepción y evaluación de proveedores.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field


# ============================================================================
# Schemas para Recepción (canónico)
# ============================================================================

class RecepcionLineaBase(BaseModel):
    """Base para línea de recepción."""
    numero_linea: int
    producto_id: int
    cantidad_solicitada: Decimal
    cantidad_recibida: Optional[Decimal] = None
    unidad_medida_id: Optional[int] = None
    lote_numero: Optional[str] = None
    fecha_vencimiento: Optional[date] = None
    estado_inspeccion: str = Field(default="NO_INSPECCIONADO")
    observaciones: Optional[str] = None


class RecepcionLineaOut(RecepcionLineaBase):
    """Salida de línea de recepción."""
    id: int
    recepcion_cabecera_id: int
    fecha_creacion: datetime
    fecha_actualizacion: datetime
    
    class Config:
        from_attributes = True


class RecepcionCabeceraBase(BaseModel):
    """Base para cabecera de recepción."""
    numero_recepcion: str
    proveedor_id: int
    fecha_recepcion: date
    fecha_entrega_esperada: Optional[date] = None
    estado: str = Field(default="PENDIENTE")
    notas: Optional[str] = None


class RecepcionCabeceraCreate(RecepcionCabeceraBase):
    """Crear recepción."""
    pass


class RecepcionCabeceraUpdate(BaseModel):
    """Actualizar recepción."""
    estado: Optional[str] = None
    fecha_entrega_esperada: Optional[date] = None
    notas: Optional[str] = None


class RecepcionCabeceraOut(RecepcionCabeceraBase):
    """Salida de cabecera de recepción."""
    id: int
    cantidad_lineas: int
    cantidad_aceptadas: int
    cantidad_rechazadas: int
    fecha_creacion: datetime
    fecha_actualizacion: datetime
    
    class Config:
        from_attributes = True


class RecepcionCabeceraDetalle(RecepcionCabeceraOut):
    """Detalle completo de recepción con líneas."""
    lineas: List[RecepcionLineaOut] = []


# ============================================================================
# Schemas para No Conformidades
# ============================================================================

class RecepcionNoConformidadBase(BaseModel):
    """Base para no conformidad."""
    codigo_nc: str
    descripcion: str
    severidad: str = Field(default="MEDIA")
    causa_raiz: Optional[str] = None
    accion_correctiva_requerida: Optional[str] = None
    estado_nc: str = Field(default="ABIERTA")


class RecepcionNoConformidadOut(RecepcionNoConformidadBase):
    """Salida de no conformidad."""
    id: int
    recepcion_linea_id: int
    usuario_creacion_id: Optional[int] = None
    fecha_cierre: Optional[date] = None
    fecha_creacion: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# Schemas para Evaluación de Proveedores
# ============================================================================

class EvaluacionProveedorMetricaBase(BaseModel):
    """Base para métrica de evaluación."""
    proveedor_id: int
    anno: int
    mes: int


class EvaluacionProveedorMetricaOut(EvaluacionProveedorMetricaBase):
    """Salida de métrica de evaluación."""
    id: int
    
    # Métricas de recepción
    cantidad_recepciones: int
    cantidad_lineas_totales: int
    cantidad_lineas_aceptadas: int
    cantidad_lineas_rechazadas: int
    porcentaje_aceptacion: Decimal
    
    # Métricas de NC
    cantidad_nc_abiertas: int
    cantidad_nc_cerradas: int
    promedio_dias_cierre_nc: Decimal
    
    # Cumplimiento
    cantidad_recepciones_a_tiempo: int
    porcentaje_cumplimiento_entrega: Decimal
    
    # Scores
    puntaje_calidad: Decimal
    puntaje_cumplimiento: Decimal
    puntaje_respuesta_nc: Decimal
    puntaje_general: Decimal
    
    # Alertas
    en_riesgo: int
    razon_riesgo: Optional[str] = None
    
    # Auditoría
    version_formula: str
    fecha_calculo: datetime
    
    class Config:
        from_attributes = True


class EvaluacionProveedorRanking(BaseModel):
    """Ranking de proveedor."""
    proveedor_id: int
    proveedor_nombre: str
    puntaje_general: Decimal
    puntaje_calidad: Decimal
    puntaje_cumplimiento: Decimal
    puntaje_respuesta_nc: Decimal
    en_riesgo: int
    razon_riesgo: Optional[str] = None
    anno: int
    mes: int


# ============================================================================
# Schemas para Importación
# ============================================================================

class RecepcionImportError(BaseModel):
    """Error durante importación."""
    fila: int
    error: str


class RecepcionImportResult(BaseModel):
    """Resultado de importación."""
    exitoso: bool
    total_filas: int
    nuevas_insertadas: int
    duplicadas: int
    errores: int
    errores_detalle: List[RecepcionImportError] = []
    timestamp: str


class RecepcionNormalizacionResult(BaseModel):
    """Resultado de normalización."""
    exitoso: bool
    total_procesadas: int
    exitosas: int
    rechazadas: int
    timestamp: str


class EvaluacionCalculoResult(BaseModel):
    """Resultado de cálculo de métricas."""
    exitoso: bool
    total_proveedores: int
    calculadas: int
    errores: int
    timestamp: str


# ============================================================================
# Schemas para Consulta
# ============================================================================

class RecepcionConsultaFiltros(BaseModel):
    """Filtros para consulta de recepciones."""
    proveedor_id: Optional[int] = None
    producto_id: Optional[int] = None
    estado: Optional[str] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    limit: int = Field(default=50, le=1000)
    offset: int = Field(default=0, ge=0)


class EvaluacionConsultaFiltros(BaseModel):
    """Filtros para consulta de evaluaciones."""
    proveedor_id: Optional[int] = None
    anno: Optional[int] = None
    mes: Optional[int] = None
    en_riesgo: Optional[int] = None
    limit: int = Field(default=50, le=1000)
    offset: int = Field(default=0, ge=0)
