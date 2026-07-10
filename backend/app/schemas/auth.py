"""Схемы аутентификации."""

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import UserSummary


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Login2FARequest(BaseModel):
    temporary_token: str
    code: str = Field(min_length=6, max_length=6)


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    requires_2fa: bool = False
    temporary_token: str | None = None
    tokens: TokenPair | None = None
    user: UserSummary | None = None


class Setup2FAResponse(BaseModel):
    secret: str
    qr_uri: str


class Verify2FARequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class Disable2FARequest(BaseModel):
    password: str
    code: str = Field(min_length=6, max_length=6)


class LogoutRequest(BaseModel):
    access_token: str
    refresh_token: str


class AcceptInviteRequest(BaseModel):
    token: str
    full_name: str
    password: str = Field(min_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)
