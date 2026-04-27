from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProveedorBase(BaseModel):
    codigo: str = Field(..., max_length=64)
    nombre: str = Field(..., max_length=160)
    contacto_nombre: Optional[str] = Field(default=None, max_length=128)
    email: Optional[str] = Field(default=None, max_length=128)
    telefono: Optional[str] = Field(default=None, max_length=64)
    cuit: Optional[str] = Field(default=None, max_length=20, description="Formato: XX-XXXXXXXX-X")
    direccion: Optional[str] = Field(default=None, max_length=255)
    localidad: Optional[str] = Field(default=None, max_length=128)
    provincia: Optional[str] = Field(default=None, max_length=128)
    notas: Optional[str] = Field(default=None, max_length=255)
    activo: bool = True


class ProveedorCreate(ProveedorBase):
    pass


class ProveedorUpdate(BaseModel):
    codigo: Optional[str] = Field(default=None, max_length=64)
    nombre: Optional[str] = Field(default=None, max_length=160)
    contacto_nombre: Optional[str] = Field(default=None, max_length=128)
    email: Optional[str] = Field(default=None, max_length=128)
    telefono: Optional[str] = Field(default=None, max_length=64)
    notas: Optional[str] = Field(default=None, max_length=255)
    activo: Optional[bool] = None


class ProveedorOut(ProveedorBase):
    id: int
    fecha_creacion: Optional[datetime]
    fecha_actualizacion: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
