from datetime import timedelta
from decimal import Decimal

import pytest


@pytest.mark.asyncio
async def test_boundary_timers(engine, now) -> None:
    state = await engine.build_initial_grid(Decimal("1000"))
    state = engine.check_boundary(state, Decimal("1000"), now)
    assert state.last_boundary_hit_at is None

    state = engine.check_boundary(state, Decimal("1400"), now)
    assert state.last_boundary_hit_at == now

    state = engine.check_boundary(state, Decimal("1100"), now)
    assert state.last_boundary_hit_at is None


@pytest.mark.asyncio
async def test_should_rebuild(engine, now) -> None:
    state = await engine.build_initial_grid(Decimal("1000"))
    state.last_boundary_hit_at = now
    assert engine.should_rebuild(state, now + timedelta(seconds=30)) is False
    assert engine.should_rebuild(state, now + timedelta(seconds=60)) is True
