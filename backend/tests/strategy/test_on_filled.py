from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.models.enums import OrderSide, StrategyType
from app.strategy.engine import GridEngine
from app.strategy.paper_executor import PaperExecutor
from app.strategy.types import GridParams


@pytest.mark.asyncio
async def test_buy_fill_places_mirror_sell(engine) -> None:
    state = await engine.build_initial_grid(Decimal("1000"))
    buy_order = next(o for o in state.orders if o.side == OrderSide.BUY and o.price == Decimal("900"))
    buy_order.filled_at = datetime.now(UTC)

    state = await engine.on_order_filled(state, buy_order)

    # В простой стратегии: купили по 900, продаём по price_sell = 950
    assert any(o.side == OrderSide.SELL and o.price_sell == Decimal("950") for o in state.orders)


@pytest.mark.asyncio
async def test_sell_fill_places_mirror_buy(engine) -> None:
    state = await engine.build_initial_grid(Decimal("1000"))
    sell_order = next(o for o in state.orders if o.side == OrderSide.SELL)
    sell_order.filled_at = datetime.now(UTC)

    state = await engine.on_order_filled(state, sell_order)

    assert any(o.side == OrderSide.BUY for o in state.orders if o.grid_index == sell_order.grid_index)


@pytest.mark.asyncio
async def test_capitalization_increases_amount() -> None:
    params = GridParams(
        strategy=StrategyType.CAPITALIZATION,
        lot_size=Decimal("0.1"),
        profit_step=Decimal("50"),
        grid_step=Decimal("100"),
        levels_above=2,
        levels_below=2,
        rebuild_timeout_sec=60,
    )
    executor = PaperExecutor(initial_base=Decimal("10"), initial_quote=Decimal("100000"), bid=Decimal("1000"), ask=Decimal("1000"))
    engine = GridEngine(params, executor)

    state = await engine.build_initial_grid(Decimal("1000"))
    # Имитируем fill sell-ордера
    sell_order = next(o for o in state.orders if o.side == OrderSide.SELL)
    sell_order.filled_at = datetime.now(UTC)
    sell_order.status = sell_order.status  # already placed

    old_total = state.total_trades
    state = await engine.on_order_filled(state, sell_order, Decimal("0.1"))

    assert state.total_trades == old_total + 1
    assert state.realized_pnl > Decimal("0")
    # Новый buy-ордер должен иметь увеличенный amount (капитализация)
    new_buys = [o for o in state.orders if o.side == OrderSide.BUY and o.grid_index == sell_order.grid_index and o.amount > Decimal("0.1")]
    assert len(new_buys) == 1


@pytest.mark.asyncio
async def test_reverse_profit_calculation() -> None:
    params = GridParams(
        strategy=StrategyType.REVERSE,
        lot_size=Decimal("0.1"),
        profit_step=Decimal("50"),
        grid_step=Decimal("100"),
        levels_above=2,
        levels_below=2,
        rebuild_timeout_sec=60,
    )
    executor = PaperExecutor(initial_base=Decimal("10"), initial_quote=Decimal("100000"), bid=Decimal("1000"), ask=Decimal("1000"))
    engine = GridEngine(params, executor)

    state = await engine.build_initial_grid(Decimal("1000"))
    sell_order = next(o for o in state.orders if o.side == OrderSide.SELL)
    sell_order.filled_at = datetime.now(UTC)

    state = await engine.on_order_filled(state, sell_order, Decimal("0.1"))
    assert state.realized_pnl > Decimal("0")
    # Реверс: profit = amount * profit_step / price
    # Новый buy должен иметь amount = old_amount + profit
    new_buys = [o for o in state.orders if o.side == OrderSide.BUY and o.grid_index == sell_order.grid_index]
    assert len(new_buys) >= 1
    assert new_buys[0].amount > Decimal("0.1")
