from typing import List, Optional

from pydantic import BaseModel, Field


class RoleBase(BaseModel):
    nombre: str = Field(min_length=1, max_length=64)
    descripcion: Optional[str] = Field(default=None, max_length=255)


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=64)
    descripcion: Optional[str] = Field(default=None, max_length=255)


class RoleOut(RoleBase):
    id: int
    user_count: Optional[int] = None


class PermissionIn(BaseModel):
    form_key: str = Field(min_length=1, max_length=64)
    puede_leer: bool = True
    puede_escribir: bool = False


class PermissionOut(PermissionIn):
    id: Optional[int] = None


class RolePerms(BaseModel):
    rol: RoleOut
    permisos: List[PermissionOut] = []
