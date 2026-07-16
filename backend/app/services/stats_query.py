"""Запрос метрик производительности из снимков статистики.

Вычисляет earnings, efficiency, drift, drawdown из GridStatSnapshot.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stats import GridStatSnapshot


@dataclass
class GridPerformance:
    """Computed performance metrics for a grid."""

    grid_id: UUID
    # Заработок
    earnings_total: Decimal
    earnings_total_pct: float
    earnings_24h: Decimal
    earnings_24h_pct: float
    earnings_1h: Decimal
    earnings_1h_pct: float
    # Эффективность
    efficiency_pct: float  # profit_math / net_asset_change
    # Дрифт
    profit_drift: Decimal  # последний
    max_drift: Decimal
    # Просадка
    max_drawdown: Decimal
    max_drawdown_pct: float
    # Текущие
    current_net_asset: Decimal
    current_price: Decimal
    total_trades: int
    placed_orders: int
    # Метки
    first_snapshot_at: datetime | None
    last_snapshot_at: datetime | None
    snapshots_count: int


async def get_grid_performance(
    db: AsyncSession,
    grid_id: UUID,
    start_amount: Decimal = Decimal("0"),
) -> GridPerformance | None:
    """Compute performance metrics from GridStatSnapshot time series."""
    result = await db.execute(
        select(GridStatSnapshot)
        .where(GridStatSnapshot.grid_id == grid_id)
        .order_by(GridStatSnapshot.time.asc())
    )
    snapshots = list(result.scalars().all())

    if not snapshots:
        return None

    now = datetime.now(UTC)
    first = snapshots[0]
    last = snapshots[-1]

    # Earnings total: last.profit_math - first.profit_math
    earnings_total = last.profit_math - first.profit_math
    first_net = first.net_asset
    earnings_total_pct = (
        float(earnings_total / first_net * 100) if first_net > 0 else 0.0
    )

    # Earnings 24h / 1h: find snapshot closest to cutoff
    def _earnings_since(cutoff: datetime) -> tuple[Decimal, float]:
        ref = first
        for s in snapshots:
            if s.time <= cutoff:
                ref = s
            else:
                break
        delta = last.profit_math - ref.profit_math
        pct = float(delta / ref.net_asset * 100) if ref.net_asset > 0 else 0.0
        return delta, pct

    earnings_24h, earnings_24h_pct = _earnings_since(now - timedelta(hours=24))
    earnings_1h, earnings_1h_pct = _earnings_since(now - timedelta(hours=1))

    # Efficiency: profit_math / abs(net_asset change)
    net_change = last.net_asset - first.net_asset
    efficiency_pct = (
        float(last.profit_math / abs(net_change) * 100)
        if net_change != 0
        else 0.0
    )

    # Drift: last and max
    max_drift = max(abs(s.profit_drift) for s in snapshots)

    # Просадка = Остаток - Стартовый объём
    # Используем start_amount если передан, иначе first snapshot net_asset
    base = start_amount if start_amount > 0 else first.net_asset
    current_drawdown = last.net_asset - base
    # Минимальная просадка за весь период (worst case)
    max_drawdown = min((s.net_asset - base) for s in snapshots)
    max_drawdown_pct = float(max_drawdown / base * 100) if base > 0 else 0.0

    return GridPerformance(
        grid_id=grid_id,
        earnings_total=earnings_total,
        earnings_total_pct=round(earnings_total_pct, 4),
        earnings_24h=earnings_24h,
        earnings_24h_pct=round(earnings_24h_pct, 4),
        earnings_1h=earnings_1h,
        earnings_1h_pct=round(earnings_1h_pct, 4),
        efficiency_pct=round(efficiency_pct, 4),
        profit_drift=last.profit_drift,
        max_drift=max_drift,
        max_drawdown=max_drawdown,
        max_drawdown_pct=round(max_drawdown_pct, 4),
        current_net_asset=last.net_asset,
        current_price=last.course,
        total_trades=last.total_trades,
        placed_orders=last.placed_orders,
        first_snapshot_at=first.time,
        last_snapshot_at=last.time,
        snapshots_count=len(snapshots),
    )


async def get_grid_stat_series(
    db: AsyncSession,
    grid_id: UUID,
    *,
    hours: int = 24,
) -> list[dict]:
    """Return raw snapshot series for charts."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    result = await db.execute(
        select(GridStatSnapshot)
        .where(
            GridStatSnapshot.grid_id == grid_id,
            GridStatSnapshot.time >= since,
        )
        .order_by(GridStatSnapshot.time.asc())
    )
    return [
        {
            "time": s.time.isoformat(),
            "price": float(s.course),
            "profit_math": float(s.profit_math),
            "net_asset": float(s.net_asset),
            "net_asset_sag": float(s.net_asset_sag),
            "profit_drift": float(s.profit_drift),
            "total_trades": s.total_trades,
            "placed_orders": s.placed_orders,
        }
        for s in result.scalars().all()
    ]
