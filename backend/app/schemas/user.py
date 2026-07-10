"""Схемы пользователей."""

from pydantic import BaseModel, EmailStr

from app.models.enums import UserRole
from app.schemas.common import UserSummary


class UserInviteCreate(BaseModel):
    email: EmailStr
    role: UserRole


class UserInviteResponse(BaseModel):
    token: str
    email: EmailStr
    role: UserRole
    invite_url: str


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: UserRole = UserRole.ADMIN


class UserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


class UserResponse(UserSummary):
    pass
