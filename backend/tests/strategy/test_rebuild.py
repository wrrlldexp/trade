from decimal import Decimal

import pytest

from app.models.enums import OrderStatus


@pytest.mark.asyncio
async def test_rebuild_grid_replaces_orders(engine) -> None:
    state = await engine.build_initial_grid(Decimal("1000"))
    old_order_ids = {order.exchange_order_id for order in state.orders}
    new_state = await engine.rebuild_grid(state, Decimal("1500"))

    assert new_state.center_price == Decimal("1500")
    assert new_state.last_boundary_hit_at is None
    assert old_order_ids.isdisjoint({order.exchange_order_id for order in new_state.orders})
    assert all(order.status == OrderStatus.CANCELLED for order in state.orders)
