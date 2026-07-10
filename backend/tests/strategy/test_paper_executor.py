from decimal import Decimal

import pytest

from app.models.enums import OrderSide, OrderStatus


@pytest.mark.asyncio
async def test_paper_executor_fills_buy_order(paper_executor) -> None:
    result = await paper_executor.place_order(OrderSide.BUY, Decimal("900"), Decimal("0.5"))
    assert await paper_executor.get_order_status(result.exchange_order_id) == OrderStatus.PLACED

    await paper_executor.set_ticker(Decimal("899"), Decimal("899"))

    assert await paper_executor.get_order_status(result.exchange_order_id) == OrderStatus.FILLED


@pytest.mark.asyncio
async def test_paper_executor_cancel(paper_executor) -> None:
    result = await paper_executor.place_order(OrderSide.SELL, Decimal("1100"), Decimal("0.5"))
    cancelled = await paper_executor.cancel_order(result.exchange_order_id)
    assert cancelled is True
    assert await paper_executor.get_order_status(result.exchange_order_id) == OrderStatus.CANCELLED
