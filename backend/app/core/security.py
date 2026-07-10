"""Безопасность: пароли и JWT."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import get_settings
from app.models.enums import UserRole

settings = get_settings()


class TokenPayload(BaseModel):
    sub: str
    typ: str
    role: str | None = None
    jti: str | None = None
    exp: int


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def _create_token(subject: str, token_type: str, expires_delta: timedelta, role: UserRole | None = None) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "typ": token_type,
        "exp": now + expires_delta,
        "iat": now,
        "jti": str(uuid.uuid4()),
    }
    if role is not None:
        payload["role"] = role.value
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: uuid.UUID, role: UserRole) -> str:
    return _create_token(
        str(user_id),
        "access",
        timedelta(minutes=settings.JWT_ACCESS_TTL_MINUTES),
        role=role,
    )


def create_refresh_token(user_id: uuid.UUID) -> str:
    return _create_token(str(user_id), "refresh", timedelta(days=settings.JWT_REFRESH_TTL_DAYS))


def create_temporary_2fa_token(user_id: uuid.UUID) -> str:
    return _create_token(
        str(user_id),
        "2fa",
        timedelta(minutes=settings.ACCESS_TOKEN_2FA_TTL_MINUTES),
    )


def decode_token(token: str) -> TokenPayload:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc
    return TokenPayload.model_validate(payload)
