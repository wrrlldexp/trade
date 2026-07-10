"""API журнала бота."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_role
from app.core.log_translator import format_for_frontend, translate_bot_log
from app.db import get_db
from app.models import BotLog, LogLevel, User, UserRole
from app.schemas.audit import BotLogListResponse, BotLogResponse, BotLogTranslation

router = APIRouter()


@router.get("/", response_model=BotLogListResponse)
async def list_logs(
    level: LogLevel | None = Query(default=None, description="Фильтр по уровню"),
    grid_id: UUID | None = Query(default=None, description="Фильтр по сетке"),
    search: str | None = Query(default=None, description="Поиск по тексту"),
    date_from: datetime | None = Query(default=None, description="Начало периода"),
    date_to: datetime | None = Query(default=None, description="Конец периода"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_role(UserRole.VIEWER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> BotLogListResponse:
    query = select(BotLog).order_by(BotLog.created_at.desc())
    count_query = select(func.count()).select_from(BotLog)

    if level:
        query = query.where(BotLog.level == level)
        count_query = count_query.where(BotLog.level == level)
    if grid_id:
        query = query.where(BotLog.grid_id == grid_id)
        count_query = count_query.where(BotLog.grid_id == grid_id)
    if search:
        query = query.where(BotLog.message.ilike(f"%{search}%"))
        count_query = count_query.where(BotLog.message.ilike(f"%{search}%"))
    if date_from:
        query = query.where(BotLog.created_at >= date_from)
        count_query = count_query.where(BotLog.created_at >= date_from)
    if date_to:
        query = query.where(BotLog.created_at <= date_to)
        count_query = count_query.where(BotLog.created_at <= date_to)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.offset(offset).limit(limit))

    items: list[BotLogResponse] = []
    for log in result.scalars().all():
        resp = BotLogResponse.model_validate(log)
        translated = translate_bot_log(
            log.message,
            level=log.level.value,
            source=log.source,
            traceback_text=log.traceback,
        )
        resp.translated = BotLogTranslation(**format_for_frontend(translated))
        items.append(resp)

    return BotLogListResponse(items=items, total=total)
