"""Audit API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_role
from app.db import get_db
from app.models import AuditLog, User, UserRole
from app.schemas.audit import AuditLogResponse

router = APIRouter()


@router.get("/", response_model=list[AuditLogResponse])
async def list_audit(
    action: str | None = Query(default=None),
    current_user: User = Depends(require_role(UserRole.VIEWER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLogResponse]:
    query = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200)
    if action:
        query = query.where(AuditLog.action == action)
    result = await db.execute(query)
    return [AuditLogResponse.model_validate(item) for item in result.scalars().all()]
