from datetime import timedelta
from decimal import Decimal

import pytest

from app.models.enums import OrderStatus


@pytest.mark.asyncio
async def test_full_scenario(engine, paper_executor, now) -> None:
    state = await engine.build_initial_grid(Decimal("1000"))

    # Двигаем цену вниз — сработает buy ордер на 900
    await paper_executor.set_ticker(Decimal("899"), Decimal("899"))
    state = await engine.tick(state, now)

    # Buy-ордер исполнился, создался mirror sell — но sell ещё не исполнен
    filled = [o for o in state.orders if o.status == OrderStatus.FILLED]
    assert len(filled) >= 1

    # Теперь двигаем цену вверх чтобы sell исполнился (sell at 950)
    await paper_executor.set_ticker(Decimal("951"), Decimal("951"))
    state = await engine.tick(state, now)

    # Теперь цикл завершён
    assert state.total_trades >= 1
    assert state.realized_pnl > Decimal("0")

    # Проверяем boundary — цена далеко за пределами
    state = engine.check_boundary(state, Decimal("1600"), now)
    assert state.last_boundary_hit_at is not None

    # Rebuild после timeout
    rebuilt = await engine.tick(state, now + timedelta(seconds=61))
    assert rebuilt.center_price >= Decimal("0")
    assert len(rebuilt.orders) >= 6
