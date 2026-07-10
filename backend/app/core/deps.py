"""FastAPI dependencies."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import is_blacklisted
from app.core.security import decode_token
from app.db import get_db
from app.models import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Email-ы, которым разрешена роль ultraadmin
ULTRAADMIN_EMAILS = {"p.krasotkin", "kuriev.mag"}


def is_ultraadmin(user: User) -> bool:
    """Проверка что пользователь ultraadmin."""
    return user.role == UserRole.ULTRAADMIN


def can_be_ultraadmin(email: str) -> bool:
    """Только определённые email могут быть ultraadmin."""
    local = email.split("@")[0].lower()
    return local in ULTRAADMIN_EMAILS


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    if payload.typ != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    if payload.jti and await is_blacklisted(payload.jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

    result = await db.execute(select(User).where(User.id == uuid.UUID(payload.sub)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_role(*roles: UserRole) -> Callable[[User], Awaitable[User]]:
    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        # ultraadmin проходит любую проверку ролей
        if current_user.role == UserRole.ULTRAADMIN:
            return current_user
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return current_user

    return dependency


def get_request_meta(request: Request) -> dict[str, str | None]:
    client_host = request.client.host if request.client else None
    return {
        "ip_address": client_host,
        "user_agent": request.headers.get("user-agent"),
    }
