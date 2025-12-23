from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RubroBase(BaseModel):
    nombre: str = Field(..., max_length=64)
    activo: Optional[bool] = True


class RubroCreate(RubroBase):
    pass


class RubroUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=64)
    activo: Optional[bool]


class RubroOut(RubroBase):
    id: int
    creado_en: Optional[datetime]
    actualizado_en: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
