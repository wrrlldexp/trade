"""Auth API."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.audit import log_action
from app.core.crypto import decrypt, encrypt
from app.core.deps import get_current_user
from app.core.redis_client import (
    add_to_blacklist,
    check_rate_limit,
    is_blacklisted,
    reset_rate_limit,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_temporary_2fa_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.totp import generate_secret, provisioning_uri, verify_code
from app.db import get_db
from app.models import User, UserInvite
from app.schemas.auth import (
    AcceptInviteRequest,
    ChangePasswordRequest,
    Disable2FARequest,
    Login2FARequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    Setup2FAResponse,
    TokenPair,
    TokenRefreshRequest,
    Verify2FARequest,
)
from app.schemas.common import UserSummary

router = APIRouter()


def _token_pair(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id),
    )


def _validate_password(password: str) -> None:
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise HTTPException(status_code=400, detail="Weak password")


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"login:{client_ip}"

    allowed = await check_rate_limit(
        rate_key,
        max_attempts=settings.LOGIN_RATE_LIMIT_ATTEMPTS,
        window_sec=settings.LOGIN_RATE_LIMIT_WINDOW_SEC,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
        )

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    await reset_rate_limit(rate_key)

    if user.totp_enabled:
        return LoginResponse(requires_2fa=True, temporary_token=create_temporary_2fa_token(user.id))

    user.last_login_at = datetime.now(UTC)
    await log_action(db, user.id, "auth.login", request=request)
    return LoginResponse(tokens=_token_pair(user), user=UserSummary.model_validate(user))


@router.post("/login/2fa", response_model=LoginResponse)
async def login_2fa(payload: Login2FARequest, request: Request, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    try:
        token = decode_token(payload.temporary_token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid temporary token") from exc
    if token.typ != "2fa":
        raise HTTPException(status_code=400, detail="Invalid temporary token")

    # H-3: 2FA-токен одноразовый — проверяем blacklist
    if token.jti and await is_blacklisted(token.jti):
        raise HTTPException(status_code=400, detail="Token already used")

    result = await db.execute(select(User).where(User.id == uuid.UUID(token.sub)))
    user = result.scalar_one_or_none()
    if user is None or not user.totp_secret_enc:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_code(decrypt(user.totp_secret_enc), payload.code):
        raise HTTPException(status_code=400, detail="Invalid 2FA code")

    # H-3: инвалидируем использованный 2FA-токен
    if token.jti:
        await add_to_blacklist(token.jti)

    user.last_login_at = datetime.now(UTC)
    await log_action(db, user.id, "auth.login_2fa", request=request)
    return LoginResponse(tokens=_token_pair(user), user=UserSummary.model_validate(user))


@router.post("/refresh", response_model=TokenPair)
async def refresh_tokens(payload: TokenRefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    try:
        token = decode_token(payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    if token.typ != "refresh":
        raise HTTPException(status_code=400, detail="Invalid token type")

    # H-2: проверяем blacklist — после logout токен недействителен
    if token.jti and await is_blacklisted(token.jti):
        raise HTTPException(status_code=401, detail="Token revoked")

    result = await db.execute(select(User).where(User.id == uuid.UUID(token.sub)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")
    return _token_pair(user)


@router.post("/logout")
async def logout(payload: LogoutRequest) -> dict[str, bool]:
    # C-1: инвалидируем оба токена — access и refresh
    for raw_token in (payload.refresh_token, payload.access_token):
        try:
            token = decode_token(raw_token)
            if token.jti:
                await add_to_blacklist(token.jti)
        except ValueError:
            pass  # logout идемпотентный — невалидный токен не ошибка
    return {"success": True}


@router.get("/me", response_model=UserSummary)
async def me(current_user: User = Depends(get_current_user)) -> UserSummary:
    return UserSummary.model_validate(current_user)


@router.post("/2fa/setup", response_model=Setup2FAResponse)
async def setup_2fa(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Setup2FAResponse:
    secret = generate_secret()
    current_user.totp_secret_enc = encrypt(secret)
    current_user.totp_enabled = False
    await db.flush()
    return Setup2FAResponse(secret=secret, qr_uri=provisioning_uri(secret, current_user.email))


@router.post("/2fa/verify")
async def enable_2fa(
    payload: Verify2FARequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    if not current_user.totp_secret_enc:
        raise HTTPException(status_code=400, detail="2FA setup not initialized")
    secret = decrypt(current_user.totp_secret_enc)
    if not verify_code(secret, payload.code):
        raise HTTPException(status_code=400, detail="Invalid 2FA code")
    current_user.totp_enabled = True
    await log_action(db, current_user.id, "auth.2fa_enable", request=request)
    return {"success": True}


@router.post("/2fa/disable")
async def disable_2fa(
    payload: Disable2FARequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    if not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid password")
    if not current_user.totp_secret_enc or not verify_code(decrypt(current_user.totp_secret_enc), payload.code):
        raise HTTPException(status_code=400, detail="Invalid 2FA code")
    current_user.totp_secret_enc = None
    current_user.totp_enabled = False
    await log_action(db, current_user.id, "auth.2fa_disable", request=request)
    return {"success": True}


@router.post("/invites/accept", response_model=UserSummary)
async def accept_invite(
    payload: AcceptInviteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserSummary:
    _validate_password(payload.password)
    result = await db.execute(select(UserInvite).where(UserInvite.token == payload.token))
    invite = result.scalar_one_or_none()
    if invite is None or invite.used_at is not None or invite.expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=404, detail="Invite not found")

    existing_user = await db.execute(select(User).where(User.email == invite.email))
    if existing_user.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="User already exists")

    user = User(
        email=invite.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=invite.role,
        created_by_id=invite.invited_by_id,
    )
    db.add(user)
    invite.used_at = datetime.now(UTC)
    await db.flush()
    await log_action(db, user.id, "auth.invite_accept", entity_type="user", entity_id=str(user.id), request=request)
    return UserSummary.model_validate(user)


@router.post("/password")
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid password")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must differ from current password")
    _validate_password(payload.new_password)
    current_user.password_hash = hash_password(payload.new_password)
    await log_action(db, current_user.id, "auth.password_change", request=request)
    return {"success": True}
