"""Тесты адаптивной стратегии."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.models.enums import OrderStatus, StrategyType
from app.strategy.engine import GridEngine
from app.strategy.paper_executor import PaperExecutor
from app.strategy.types import GridParams, Ticker


@pytest.fixture()
def adaptive_params() -> GridParams:
    return GridParams(
        strategy=StrategyType.ADAPTIVE,
        lot_size=Decimal("0.1"),
        profit_step=Decimal("50"),
        grid_step=Decimal("100"),
        levels_above=5,
        levels_below=5,
        rebuild_timeout_sec=3600,
        adaptive_timer_sec=15,
        prepay_base=Decimal("0.5"),
        prepay_quote=Decimal("5000"),
        prepay_amount=Decimal("0.05"),
    )


@pytest.fixture()
def adaptive_executor() -> PaperExecutor:
    return PaperExecutor(
        initial_base=Decimal("10"),
        initial_quote=Decimal("100000"),
        bid=Decimal("1000"),
        ask=Decimal("1000"),
    )


@pytest.fixture()
def adaptive_engine(adaptive_params: GridParams, adaptive_executor: PaperExecutor) -> GridEngine:
    return GridEngine(adaptive_params, adaptive_executor)


@pytest.mark.asyncio
async def test_adaptive_builds_subgrid(adaptive_engine, adaptive_executor) -> None:
    state = await adaptive_engine.build_initial_grid(Decimal("1000"))
    assert len(state.orders) == 10
    assert state.adaptive_top_idx is None  # подсетка ещё не построена

    ticker = Ticker(bid=Decimal("1000"), ask=Decimal("1000"))
    state = adaptive_engine.build_adaptive_subgrid(state, ticker)

    # Подсетка должна быть построена
    assert state.adaptive_top_idx is not None
    assert state.adaptive_bottom_idx is not None

    # У некоторых ордеров должен быть prepay
    orders_with_prepay = [o for o in state.orders if o.prepay > 0]
    assert len(orders_with_prepay) > 0


@pytest.mark.asyncio
async def test_adaptive_tick_fills_and_flips(adaptive_engine, adaptive_executor) -> None:
    state = await adaptive_engine.build_initial_grid(Decimal("1000"))
    now = datetime.now(UTC)

    # Двигаем цену вниз чтобы сработал buy
    await adaptive_executor.set_ticker(Decimal("899"), Decimal("899"))
    state, _ = await adaptive_engine.tick(state, now)

    # Должен произойти fill и flip
    filled = [o for o in state.orders if o.status == OrderStatus.FILLED]
    assert len(filled) >= 1


@pytest.mark.asyncio
async def test_adaptive_cap_strategy() -> None:
    params = GridParams(
        strategy=StrategyType.ADAPTIVE_CAPITALIZATION,
        lot_size=Decimal("0.1"),
        profit_step=Decimal("50"),
        grid_step=Decimal("100"),
        levels_above=3,
        levels_below=3,
        rebuild_timeout_sec=3600,
        adaptive_timer_sec=15,
        prepay_base=Decimal("0.3"),
        prepay_quote=Decimal("3000"),
        prepay_amount=Decimal("0.05"),
    )
    executor = PaperExecutor(
        initial_base=Decimal("10"),
        initial_quote=Decimal("100000"),
        bid=Decimal("1000"),
        ask=Decimal("1000"),
    )
    engine = GridEngine(params, executor)

    state = await engine.build_initial_grid(Decimal("1000"))
    assert len(state.orders) == 6
    assert engine._is_adaptive is True
    assert engine._is_capitalization is True
