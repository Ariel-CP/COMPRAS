from typing import Dict, List

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=4)
    remember_me: bool = False


class Permission(BaseModel):
    puede_leer: bool
    puede_escribir: bool


class UserPublic(BaseModel):
    id: int
    email: EmailStr
    nombre: str | None = None
    roles: List[str] = []
    permissions: Dict[str, Permission] = {}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class MeResponse(UserPublic):
    pass


class SessionInfo(BaseModel):
    jti: str
    created_at: str
    last_used_at: str | None = None
    expires_at: str
    persistent: bool = False
    revoked: bool = False
    ip: str | None = None
    user_agent: str | None = None
    device_name: str | None = None
