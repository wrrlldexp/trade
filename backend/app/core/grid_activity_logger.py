"""Детальный логгер активности сетки — отдельный от bot_logger.

Пишет в таблицу grid_activity_logs структурированную информацию:
- каждый тик с ценой, количеством ордеров, PnL
- каждый fill (покупка/продажа) с деталями
- перестроения и сдвиги сетки
- статистика API-вызовов (req/s, req/h)
- старт/стоп и ошибки

Fire-and-forget: не блокирует тик-луп, ошибки записи молча проглатываются.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.db import AsyncSessionLocal
from app.models.audit import GridActivityLog


class ApiCallCounter:
    """Считает API-вызовы за скользящее окно (1 час)."""

    def __init__(self) -> None:
        self._calls: list[float] = []
        self._window: float = 3600.0  # 1 час

    def record(self) -> None:
        self._calls.append(time.monotonic())

    def _prune(self) -> None:
        cutoff = time.monotonic() - self._window
        self._calls = [t for t in self._calls if t > cutoff]

    @property
    def per_hour(self) -> int:
        self._prune()
        return len(self._calls)

    @property
    def per_second(self) -> float:
        self._prune()
        if not self._calls:
            return 0.0
        span = time.monotonic() - self._calls[0]
        if span < 1:
            return float(len(self._calls))
        return round(len(self._calls) / span, 2)

    @property
    def total(self) -> int:
        return len(self._calls)


# Per-grid API counters (executor_id → counter)
_api_counters: dict[uuid.UUID, ApiCallCounter] = {}


def get_api_counter(grid_id: uuid.UUID) -> ApiCallCounter:
    if grid_id not in _api_counters:
        _api_counters[grid_id] = ApiCallCounter()
    return _api_counters[grid_id]


def remove_api_counter(grid_id: uuid.UUID) -> None:
    _api_counters.pop(grid_id, None)


async def _write(
    grid_id: uuid.UUID,
    event: str,
    data: dict,
) -> None:
    """Fire-and-forget запись в БД."""
    try:
        async with AsyncSessionLocal() as session:
            entry = GridActivityLog(
                grid_id=grid_id,
                event=event,
                data=data,
            )
            session.add(entry)
            await session.commit()
    except Exception:
        pass  # Не ломаем тик-луп из-за логов


async def log_tick(
    grid_id: uuid.UUID,
    *,
    bid: Decimal,
    ask: Decimal,
    spread: Decimal,
    placed_orders: int,
    filled_orders: int,
    total_trades: int,
    realized_pnl: Decimal,
    tick_duration_ms: float,
    equity: Decimal | None = None,
) -> None:
    counter = get_api_counter(grid_id)
    data: dict = {
        "bid": str(bid),
        "ask": str(ask),
        "spread": str(spread),
        "placed_orders": placed_orders,
        "filled_orders": filled_orders,
        "total_trades": total_trades,
        "realized_pnl": str(realized_pnl),
        "tick_ms": round(tick_duration_ms, 1),
        "api_req_per_sec": counter.per_second,
        "api_req_per_hour": counter.per_hour,
    }
    if equity is not None:
        data["equity"] = str(equity)
    await _write(grid_id, "tick", data)


async def log_fill(
    grid_id: uuid.UUID,
    *,
    side: str,
    price: Decimal,
    price_sell: Decimal,
    amount: Decimal,
    profit: Decimal,
    total_trades: int,
    realized_pnl: Decimal,
) -> None:
    await _write(grid_id, "fill", {
        "side": side,
        "price": str(price),
        "price_sell": str(price_sell),
        "amount": str(amount),
        "profit": str(profit),
        "total_trades": total_trades,
        "realized_pnl": str(realized_pnl),
    })


async def log_rebuild(
    grid_id: uuid.UUID,
    *,
    reason: str,
    old_center: Decimal,
    new_center: Decimal,
    cancelled_orders: int,
    new_orders: int,
) -> None:
    await _write(grid_id, "rebuild", {
        "reason": reason,
        "old_center": str(old_center),
        "new_center": str(new_center),
        "cancelled_orders": cancelled_orders,
        "new_orders": new_orders,
    })


async def log_shift(
    grid_id: uuid.UUID,
    *,
    direction: str,
    delta: Decimal,
    current_price: Decimal,
    cancelled_orders: int,
    new_orders: int,
) -> None:
    await _write(grid_id, "shift", {
        "direction": direction,
        "delta": str(delta),
        "current_price": str(current_price),
        "cancelled_orders": cancelled_orders,
        "new_orders": new_orders,
    })


async def log_grid_start(
    grid_id: uuid.UUID,
    *,
    name: str,
    symbol: str,
    strategy: str,
    mode: str,
    center_price: Decimal,
    levels: int,
    tick_interval: float,
) -> None:
    await _write(grid_id, "start", {
        "name": name,
        "symbol": symbol,
        "strategy": strategy,
        "mode": mode,
        "center_price": str(center_price),
        "levels": levels,
        "tick_interval": tick_interval,
    })


async def log_grid_stop(
    grid_id: uuid.UUID,
    *,
    name: str,
    total_trades: int,
    realized_pnl: Decimal,
    reason: str = "manual",
) -> None:
    counter = get_api_counter(grid_id)
    await _write(grid_id, "stop", {
        "name": name,
        "total_trades": total_trades,
        "realized_pnl": str(realized_pnl),
        "reason": reason,
        "api_total_calls": counter.total,
        "api_req_per_hour": counter.per_hour,
    })
    remove_api_counter(grid_id)


async def log_error(
    grid_id: uuid.UUID,
    *,
    error: str,
    context: str,
) -> None:
    await _write(grid_id, "error", {
        "error": error[:500],
        "context": context,
    })


async def log_api_stats(
    grid_id: uuid.UUID,
) -> None:
    """Периодическая запись API-статистики (вызывается из worker)."""
    counter = get_api_counter(grid_id)
    await _write(grid_id, "api_stats", {
        "req_per_second": counter.per_second,
        "req_per_hour": counter.per_hour,
        "total_calls": counter.total,
    })
