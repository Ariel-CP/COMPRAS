from typing import Optional, List
from pydantic import BaseModel, Field


class MBOMCabecera(BaseModel):
    id: Optional[int] = None
    producto_padre_id: int
    revision: str = Field(default="A")
    estado: str = Field(pattern=r"^(BORRADOR|ACTIVO|ARCHIVADO)$")
    vigencia_desde: Optional[str] = None
    vigencia_hasta: Optional[str] = None
    notas: Optional[str] = None


class MBOMDetalleLinea(BaseModel):
    id: Optional[int] = None
    mbom_id: int
    renglon: int
    componente_producto_id: int
    componente_codigo: Optional[str] = None
    componente_nombre: Optional[str] = None
    componente_tipo_producto: Optional[str] = None
    cantidad: float
    unidad_medida_id: int
    unidad_medida_codigo: Optional[str] = None
    factor_merma: float = 0.0
    operacion_secuencia: Optional[int] = None
    grupo_alternativa: Optional[str] = None
    designador_referencia: Optional[str] = None
    notas: Optional[str] = None


class MBOMEstructura(BaseModel):
    cabecera: MBOMCabecera
    lineas: List[MBOMDetalleLinea]
