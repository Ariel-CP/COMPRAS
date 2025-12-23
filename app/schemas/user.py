from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    nombre: str = Field(min_length=1, max_length=128)
    activo: bool = True
    roles: List[str] = []


class UserCreate(UserBase):
    password: str = Field(min_length=6, max_length=128)


class UserUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=128)
    password: Optional[str] = Field(default=None, min_length=6, max_length=128)
    activo: Optional[bool] = None
    roles: Optional[List[str]] = None


class UserOut(UserBase):
    id: int
    fecha_creacion: Optional[str] = None
