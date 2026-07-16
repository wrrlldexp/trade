"""Типы ядра стратегии."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, computed_field

from app.models.enums import OrderSide, OrderStatus, StrategyType


class StrategyModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)


class OrderResult(StrategyModel):
    exchange_order_id: str
    success: bool
    error: str | None = None


class Ticker(StrategyModel):
    bid: Decimal
    ask: Decimal

    @computed_field  # type: ignore[prop-decorator]
    @property
    def mid(self) -> Decimal:
        return (self.bid + self.ask) / Decimal("2")


class Balance(StrategyModel):
    base: Decimal = Decimal("0")
    quote: Decimal = Decimal("0")


class GridParams(StrategyModel):
    strategy: StrategyType = StrategyType.SIMPLE
    lot_size: Decimal
    lot_quote: Decimal | None = None  # Лот в quote-валюте → пересчёт amount по цене
    profit_step: Decimal
    grid_step: Decimal
    levels_above: int
    levels_below: int
    rebuild_timeout_sec: int = 3600
    fee: Decimal = Decimal("0.001")  # Комиссия биржи (0.1% = 0.001)


class PlannedOrder(StrategyModel):
    side: OrderSide
    price: Decimal
    amount: Decimal


@dataclass(slots=True)
class LiveOrder:
    id: uuid.UUID
    side: OrderSide
    price: Decimal
    amount: Decimal
    status: OrderStatus
    exchange_order_id: str
    grid_index: int = 0
    price_sell: Decimal = Decimal("0")
    profit: Decimal = Decimal("0")
    count_complete: int = 0
    created_at: datetime | None = None
    filled_at: datetime | None = None


@dataclass(slots=True)
class GridState:
    center_price: Decimal
    orders: list[LiveOrder] = field(default_factory=list)
    last_boundary_hit_at: datetime | None = None
    realized_pnl: Decimal = Decimal("0")
    total_trades: int = 0
