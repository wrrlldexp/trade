"""Users API."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.deps import can_be_ultraadmin, is_ultraadmin, require_role
from app.core.security import hash_password
from app.db import get_db
from app.models import User, UserInvite, UserRole
from app.schemas.user import (
    UserCreate,
    UserInviteCreate,
    UserInviteResponse,
    UserResponse,
    UserUpdate,
)

router = APIRouter()


def _check_ultraadmin_guard(current_user: User, target_role: UserRole | None = None, target_user: User | None = None) -> None:
    """Защита ultraadmin:
    - Назначить ultraadmin может только ultraadmin с разрешённым email
    - Изменять/удалять ultraadmin может только другой ultraadmin
    """
    if target_role == UserRole.ULTRAADMIN and not is_ultraadmin(current_user):
        raise HTTPException(status_code=403, detail="Только ultraadmin может назначать ultraadmin")
    if target_user and target_user.role == UserRole.ULTRAADMIN and not is_ultraadmin(current_user):
        raise HTTPException(status_code=403, detail="Нельзя изменять ultraadmin")


@router.get("/", response_model=list[UserResponse])
async def list_users(
    current_user: User = Depends(require_role(UserRole.VIEWER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = list(result.scalars().all())
    # Ultraadmin невидимы для обычных пользователей
    if not is_ultraadmin(current_user):
        users = [u for u in users if u.role != UserRole.ULTRAADMIN]
    return [UserResponse.model_validate(user) for user in users]


@router.post("/", response_model=UserResponse)
async def create_user(
    payload: UserCreate,
    request: Request,
    current_user: User = Depends(require_role(UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="User already exists")

    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    # Защита назначения ultraadmin
    _check_ultraadmin_guard(current_user, target_role=payload.role)
    if payload.role == UserRole.ULTRAADMIN and not can_be_ultraadmin(payload.email):
        raise HTTPException(status_code=403, detail="Этот email не может быть ultraadmin")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        is_active=True,
        created_by_id=current_user.id,
    )
    db.add(user)
    await db.flush()
    await log_action(
        db, current_user.id, "user.create", entity_type="user", entity_id=str(user.id), request=request
    )
    return UserResponse.model_validate(user)


@router.post("/invites", response_model=UserInviteResponse)
async def create_invite(
    payload: UserInviteCreate,
    request: Request,
    current_user: User = Depends(require_role(UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> UserInviteResponse:
    # ultraadmin нельзя назначить по инвайту
    if payload.role == UserRole.ULTRAADMIN:
        raise HTTPException(status_code=403, detail="Ultraadmin нельзя назначить через инвайт")
    token = secrets.token_urlsafe(24)
    invite = UserInvite(
        email=payload.email,
        role=payload.role,
        token=token,
        invited_by_id=current_user.id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db.add(invite)
    await db.flush()
    await log_action(db, current_user.id, "user.invite", entity_type="user_invite", entity_id=str(invite.id), request=request)
    return UserInviteResponse(
        token=token,
        email=payload.email,
        role=payload.role,
        invite_url=f"/invite/{token}",
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    request: Request,
    current_user: User = Depends(require_role(UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Защита: нельзя менять ultraadmin если ты не ultraadmin
    _check_ultraadmin_guard(current_user, target_role=payload.role, target_user=user)

    # Назначить ultraadmin может только ultraadmin + проверка email
    if payload.role == UserRole.ULTRAADMIN and not can_be_ultraadmin(user.email):
        raise HTTPException(status_code=403, detail="Этот email не может быть ultraadmin")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    await log_action(db, current_user.id, "user.update", entity_type="user", entity_id=str(user.id), request=request)
    return UserResponse.model_validate(user)


@router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: UUID,
    payload: dict,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ULTRAADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Сброс пароля пользователя (только ultraadmin)."""
    new_password = payload.get("new_password", "")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Пароль должен быть не менее 8 символов")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Используйте смену пароля в профиле")

    user.password_hash = hash_password(new_password)
    await log_action(
        db, current_user.id, "user.reset_password",
        entity_type="user", entity_id=str(user.id), request=request,
    )
    return {"success": True}


@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    request: Request,
    current_user: User = Depends(require_role(UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Нельзя удалить ultraadmin
    _check_ultraadmin_guard(current_user, target_user=user)

    # Нельзя удалить себя
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя удалить свой аккаунт")

    # Ultraadmin — полное удаление, остальные — деактивация (мягкое) или удаление (ultraadmin решает)
    if is_ultraadmin(current_user):
        # Ultraadmin может полностью удалить аккаунт
        await db.delete(user)
        action = "user.hard_delete"
    else:
        # Superadmin — мягкое удаление
        user.is_active = False
        action = "user.deactivate"

    await log_action(db, current_user.id, action, entity_type="user", entity_id=str(user.id), request=request)
    return {"success": True, "action": action}
