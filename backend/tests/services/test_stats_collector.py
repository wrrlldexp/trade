"""Tests for GridStatsCollector and stats_query."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import OrderStatus
from app.services.stats_collector import GridStatsCollector, StatsCollectReport
from app.services.stats_query import GridPerformance, get_grid_performance, get_grid_stat_series


def _mock_db(rows):
    """Create a mock async db session that returns rows from execute()."""
    db = AsyncMock()
    scalars_obj = MagicMock()
    scalars_obj.all.return_value = rows
    result_obj = MagicMock()
    result_obj.scalars.return_value = scalars_obj
    db.execute.return_value = result_obj
    return db


# ─── Fixtures ───


class FakeTicker:
    def __init__(self, mid: Decimal):
        self.bid = mid
        self.ask = mid
        self.mid = mid


class FakeBalance:
    def __init__(self, base: Decimal, quote: Decimal):
        self.base = base
        self.quote = quote


class FakeOrder:
    def __init__(self, status: OrderStatus):
        self.status = status


class FakeState:
    def __init__(self, realized_pnl: Decimal = Decimal("10"), total_trades: int = 5, orders=None):
        self.realized_pnl = realized_pnl
        self.total_trades = total_trades
        self.orders = orders or []


class FakeGrid:
    def __init__(self, grid_id=None, account_id=None, symbol="BTC/USDT"):
        self.id = grid_id or uuid.uuid4()
        self.account_id = account_id or uuid.uuid4()
        self.symbol = symbol
        self.status = MagicMock()
        self.status.value = "running"
        self.account = MagicMock()
        self.realized_pnl = Decimal("0")
        self.total_trades = 0


class FakeExchange:
    async def fetch_balance(self):
        return {
            "total": {"BTC": 1.0, "USDT": 50000.0},
            "free": {"BTC": 0.5, "USDT": 25000.0},
        }


# ─── StatsCollectReport ───


def test_report_defaults():
    r = StatsCollectReport()
    assert r.accounts_processed == 0
    assert r.grids_processed == 0
    assert r.grids_skipped == 0
    assert r.errors == []


# ─── GridStatsCollector unit tests ───


def test_collector_init():
    factory = MagicMock()
    collector = GridStatsCollector(factory, interval_sec=30)
    assert collector._interval_sec == 30
    assert collector._prev_net_assets == {}


# ─── stats_query tests (using mock DB) ───


class FakeSnapshot:
    def __init__(self, time, profit_math, net_asset, course, profit_drift, total_trades, placed_orders, net_asset_sag=Decimal("0")):
        self.time = time
        self.profit_math = Decimal(str(profit_math))
        self.net_asset = Decimal(str(net_asset))
        self.course = Decimal(str(course))
        self.profit_drift = Decimal(str(profit_drift))
        self.total_trades = total_trades
        self.placed_orders = placed_orders
        self.net_asset_sag = Decimal(str(net_asset_sag))


@pytest.mark.asyncio
async def test_get_grid_performance_empty():
    """No snapshots -> returns None."""
    db = _mock_db([])
    perf = await get_grid_performance(db, uuid.uuid4())
    assert perf is None


@pytest.mark.asyncio
async def test_get_grid_performance_single_snapshot():
    """Single snapshot: earnings=0, drawdown=0."""
    grid_id = uuid.uuid4()
    now = datetime.now(UTC)
    snap = FakeSnapshot(
        time=now, profit_math=10, net_asset=1000,
        course=50000, profit_drift=0.5, total_trades=5, placed_orders=3,
    )
    db = _mock_db([snap])

    perf = await get_grid_performance(db, grid_id)
    assert perf is not None
    assert perf.grid_id == grid_id
    assert perf.earnings_total == Decimal("0")
    assert perf.snapshots_count == 1
    assert perf.total_trades == 5
    assert perf.placed_orders == 3


@pytest.mark.asyncio
async def test_get_grid_performance_multiple_snapshots():
    """Multiple snapshots: computes earnings, drawdown."""
    grid_id = uuid.uuid4()
    now = datetime.now(UTC)
    snaps = [
        FakeSnapshot(time=now - timedelta(hours=2), profit_math=0, net_asset=1000, course=50000, profit_drift=0, total_trades=0, placed_orders=5),
        FakeSnapshot(time=now - timedelta(hours=1), profit_math=5, net_asset=1005, course=50100, profit_drift=0.1, total_trades=3, placed_orders=4),
        FakeSnapshot(time=now, profit_math=12, net_asset=990, course=49500, profit_drift=0.5, total_trades=7, placed_orders=5),
    ]
    db = _mock_db(snaps)

    perf = await get_grid_performance(db, grid_id)
    assert perf is not None
    assert perf.earnings_total == Decimal("12")
    assert perf.earnings_total_pct == round(12 / 1000 * 100, 4)
    assert perf.max_drawdown < 0  # net_asset dropped from 1005 to 990
    assert perf.total_trades == 7
    assert perf.snapshots_count == 3


@pytest.mark.asyncio
async def test_get_grid_performance_drawdown():
    """Drawdown calculated from peak to trough."""
    grid_id = uuid.uuid4()
    now = datetime.now(UTC)
    snaps = [
        FakeSnapshot(time=now - timedelta(minutes=3), profit_math=0, net_asset=1000, course=50000, profit_drift=0, total_trades=0, placed_orders=5),
        FakeSnapshot(time=now - timedelta(minutes=2), profit_math=10, net_asset=1100, course=51000, profit_drift=0, total_trades=2, placed_orders=5),
        FakeSnapshot(time=now - timedelta(minutes=1), profit_math=15, net_asset=900, course=48000, profit_drift=1, total_trades=4, placed_orders=5),
        FakeSnapshot(time=now, profit_math=20, net_asset=1050, course=50500, profit_drift=0.5, total_trades=6, placed_orders=5),
    ]
    db = _mock_db(snaps)

    perf = await get_grid_performance(db, grid_id)
    # Просадка = Остаток - Старт. base = first.net_asset = 1000
    # min(1000-1000, 1100-1000, 900-1000, 1050-1000) = -100
    assert perf.max_drawdown == Decimal("-100")
    assert perf.max_drawdown_pct == round(-100 / 1000 * 100, 4)


@pytest.mark.asyncio
async def test_get_grid_performance_earnings_periods():
    """Earnings 24h and 1h computed correctly."""
    grid_id = uuid.uuid4()
    now = datetime.now(UTC)
    snaps = [
        FakeSnapshot(time=now - timedelta(hours=48), profit_math=0, net_asset=1000, course=50000, profit_drift=0, total_trades=0, placed_orders=5),
        FakeSnapshot(time=now - timedelta(hours=23), profit_math=20, net_asset=1020, course=50100, profit_drift=0, total_trades=5, placed_orders=5),
        FakeSnapshot(time=now - timedelta(minutes=30), profit_math=35, net_asset=1035, course=50200, profit_drift=0.1, total_trades=8, placed_orders=4),
        FakeSnapshot(time=now, profit_math=40, net_asset=1040, course=50300, profit_drift=0.2, total_trades=10, placed_orders=5),
    ]
    db = _mock_db(snaps)

    perf = await get_grid_performance(db, grid_id)
    assert perf.earnings_total == Decimal("40")
    assert perf.earnings_24h == Decimal("40")
    # 1h: ref = snap[1] (23h ago, last one <= cutoff)
    assert perf.earnings_1h == Decimal("20")


@pytest.mark.asyncio
async def test_get_grid_stat_series():
    """Returns dict series from snapshots."""
    grid_id = uuid.uuid4()
    now = datetime.now(UTC)
    snap = FakeSnapshot(
        time=now, profit_math=10, net_asset=1000, course=50000,
        profit_drift=0.5, total_trades=5, placed_orders=3, net_asset_sag=Decimal("2"),
    )
    db = _mock_db([snap])

    series = await get_grid_stat_series(db, grid_id, hours=24)
    assert len(series) == 1
    assert series[0]["price"] == 50000.0
    assert series[0]["profit_math"] == 10.0
    assert series[0]["net_asset"] == 1000.0
    assert series[0]["profit_drift"] == 0.5
    assert series[0]["total_trades"] == 5
    assert series[0]["placed_orders"] == 3


@pytest.mark.asyncio
async def test_get_grid_stat_series_empty():
    """No snapshots in period."""
    db = _mock_db([])
    series = await get_grid_stat_series(db, uuid.uuid4(), hours=1)
    assert series == []


@pytest.mark.asyncio
async def test_get_grid_performance_efficiency():
    """Efficiency = profit_math / |net_asset_change| * 100."""
    grid_id = uuid.uuid4()
    now = datetime.now(UTC)
    snaps = [
        FakeSnapshot(time=now - timedelta(hours=1), profit_math=0, net_asset=1000, course=50000, profit_drift=0, total_trades=0, placed_orders=5),
        FakeSnapshot(time=now, profit_math=50, net_asset=1020, course=50100, profit_drift=1, total_trades=10, placed_orders=5),
    ]
    db = _mock_db(snaps)

    perf = await get_grid_performance(db, grid_id)
    assert perf.efficiency_pct == 250.0


@pytest.mark.asyncio
async def test_get_grid_performance_max_drift():
    """Max drift is max absolute value of profit_drift across all snapshots."""
    grid_id = uuid.uuid4()
    now = datetime.now(UTC)
    snaps = [
        FakeSnapshot(time=now - timedelta(minutes=2), profit_math=0, net_asset=1000, course=50000, profit_drift=Decimal("0.5"), total_trades=0, placed_orders=5),
        FakeSnapshot(time=now - timedelta(minutes=1), profit_math=5, net_asset=1005, course=50100, profit_drift=Decimal("-3.2"), total_trades=3, placed_orders=4),
        FakeSnapshot(time=now, profit_math=10, net_asset=1010, course=50200, profit_drift=Decimal("1.0"), total_trades=5, placed_orders=5),
    ]
    db = _mock_db(snaps)

    perf = await get_grid_performance(db, grid_id)
    assert perf.max_drift == Decimal("3.2")
    assert perf.profit_drift == Decimal("1.0")
