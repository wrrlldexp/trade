from decimal import Decimal

import pytest

from app.models.enums import OrderSide


@pytest.mark.asyncio
async def test_build_grid_places_expected_orders(engine) -> None:
    state = await engine.build_initial_grid(Decimal("1000"))
    assert len(state.orders) == 6
    buy_orders = [o for o in state.orders if o.side == OrderSide.BUY]
    sell_orders = [o for o in state.orders if o.side == OrderSide.SELL]
    buy_prices = [o.price for o in buy_orders]
    sell_prices = [o.price_sell for o in sell_orders]
    assert buy_prices == [Decimal("900"), Decimal("800"), Decimal("700")]
    # sell: price_sell = center + grid_step * level = 1100, 1200, 1300
    assert sell_prices == [Decimal("1100"), Decimal("1200"), Decimal("1300")]

    # Каждый buy-ордер имеет price_sell = price + profit_step
    for order in buy_orders:
        assert order.price_sell == order.price + Decimal("50")

    # Проверяем grid_index
    for i, order in enumerate(state.orders):
        assert order.grid_index == i
