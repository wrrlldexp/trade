"""Общие схемы."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import (
    GridMode,
    GridStatus,
    OrderSide,
    OrderStatus,
    StrategyType,
    TradeEventType,
    UserRole,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserSummary(ORMModel):
    id: UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    totp_enabled: bool
    created_at: datetime


class GridOrderResponse(ORMModel):
    id: UUID
    grid_index: int
    side: OrderSide
    status: OrderStatus
    price: Decimal
    price_sell: Decimal
    amount: Decimal
    exchange_order_id: str | None
    profit: Decimal
    count_complete: int
    created_at: datetime
    filled_at: datetime | None


class TradeEventResponse(ORMModel):
    id: int
    event_type: TradeEventType
    price: Decimal | None
    amount: Decimal | None
    pnl_delta: Decimal | None
    payload: dict | None
    created_at: datetime


class GridResponse(ORMModel):
    id: UUID
    account_id: UUID
    name: str
    symbol: str
    mode: GridMode
    status: GridStatus
    strategy: StrategyType
    lot_size: Decimal
    lot_quote: Decimal | None = None
    profit_step: Decimal
    grid_step: Decimal
    levels_above: int
    levels_below: int
    rebuild_timeout_sec: int
    last_boundary_hit_at: datetime | None
    # Тик
    tick_interval_sec: float
    # Статистика
    total_trades: int
    realized_pnl: Decimal
    # Авто-конвертация
    auto_convert_to: str | None = None
    unconverted_pnl: Decimal = Decimal("0")
    created_at: datetime
    started_at: datetime | None
    stopped_at: datetime | None
