"""API истории сделок."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_role
from app.db import get_db
from app.models import ExchangeAccount, Grid, TradeEvent, User, UserRole
from app.schemas.audit import TradeEventEnrichedResponse

router = APIRouter()


@router.get("/", response_model=list[TradeEventEnrichedResponse])
async def list_trades(
    grid_id: UUID | None = Query(default=None, description="Фильтр по сетке"),
    event_type: str | None = Query(default=None, description="Тип события"),
    date_from: datetime | None = Query(default=None, description="Начало периода"),
    date_to: datetime | None = Query(default=None, description="Конец периода"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_role(UserRole.VIEWER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[TradeEventEnrichedResponse]:
    query = (
        select(TradeEvent, Grid.name.label("grid_name"), Grid.symbol)
        .join(Grid, Grid.id == TradeEvent.grid_id)
        .join(ExchangeAccount, ExchangeAccount.id == Grid.account_id)
        .order_by(TradeEvent.created_at.desc())
    )

    # M-6: фильтр по владельцу — ADMIN видит только свои, SUPERADMIN/VIEWER — все
    if current_user.role == UserRole.ADMIN:
        query = query.where(ExchangeAccount.owner_id == current_user.id)

    if grid_id:
        query = query.where(TradeEvent.grid_id == grid_id)
    if event_type:
        query = query.where(TradeEvent.event_type == event_type)
    if date_from:
        query = query.where(TradeEvent.created_at >= date_from)
    if date_to:
        query = query.where(TradeEvent.created_at <= date_to)

    result = await db.execute(query.offset(offset).limit(limit))
    rows = result.all()

    return [
        TradeEventEnrichedResponse(
            id=te.id,
            grid_id=te.grid_id,
            grid_name=grid_name,
            symbol=symbol,
            event_type=te.event_type.value,
            price=str(te.price) if te.price else None,
            amount=str(te.amount) if te.amount else None,
            pnl_delta=str(te.pnl_delta) if te.pnl_delta else None,
            payload=te.payload,
            created_at=te.created_at,
        )
        for te, grid_name, symbol in rows
    ]
