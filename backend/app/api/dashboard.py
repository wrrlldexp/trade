"""Dashboard API — агрегированная статистика по сеткам пользователя."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_role
from app.db import get_db
from app.models import ExchangeAccount, Grid, GridStatus, TradeEvent, User, UserRole
from app.models.enums import OrderSide, OrderStatus, TradeEventType
from app.models.grid import GridOrder

router = APIRouter()


class StrategyStats(BaseModel):
    strategy: str
    grids_count: int
    active_count: int
    total_pnl: float
    total_trades: int


class PositionSummary(BaseModel):
    grid_id: str
    grid_name: str
    symbol: str
    strategy: str
    status: str
    mode: str
    side: str
    entry_price: float
    current_levels: int
    filled_orders: int
    realized_pnl: float
    total_trades: int
    auto_convert_to: str | None = None
    unconverted_pnl: float = 0.0


class DashboardResponse(BaseModel):
    total_grids: int
    active_grids: int
    total_pnl: float
    total_trades: int
    win_rate: float
    strategies: list[StrategyStats]
    positions: list[PositionSummary]
    equity_curve: list[dict]


@router.get("/", response_model=DashboardResponse)
async def get_dashboard(
    current_user: User = Depends(require_role(UserRole.VIEWER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    query = (
        select(Grid)
        .join(ExchangeAccount, ExchangeAccount.id == Grid.account_id)
        .order_by(Grid.created_at.desc())
    )
    if current_user.role == UserRole.ADMIN:
        query = query.where(ExchangeAccount.owner_id == current_user.id)
    result = await db.execute(query)
    grids = list(result.scalars().all())

    total_grids = len(grids)
    active_grids = sum(1 for g in grids if g.status == GridStatus.RUNNING)
    total_pnl = float(sum(g.realized_pnl for g in grids))
    total_trades = sum(g.total_trades for g in grids)

    grids_with_trades = [g for g in grids if g.total_trades > 0]
    winning = sum(1 for g in grids_with_trades if g.realized_pnl > 0)
    win_rate = (winning / len(grids_with_trades) * 100) if grids_with_trades else 0.0

    strategy_map: dict[str, StrategyStats] = {}
    for g in grids:
        key = g.strategy.value
        if key not in strategy_map:
            strategy_map[key] = StrategyStats(strategy=key, grids_count=0, active_count=0, total_pnl=0.0, total_trades=0)
        s = strategy_map[key]
        s.grids_count += 1
        if g.status == GridStatus.RUNNING:
            s.active_count += 1
        s.total_pnl += float(g.realized_pnl)
        s.total_trades += g.total_trades
    strategies = list(strategy_map.values())

    grid_ids = [g.id for g in grids]
    order_stats: dict = {}
    avg_prices: dict = {}

    if grid_ids:
        order_result = await db.execute(
            select(
                GridOrder.grid_id,
                func.count(GridOrder.id).label("total"),
                func.count(GridOrder.id).filter(GridOrder.status == OrderStatus.FILLED).label("filled"),
            )
            .where(GridOrder.grid_id.in_(grid_ids))
            .group_by(GridOrder.grid_id)
        )
        for row in order_result.all():
            order_stats[row.grid_id] = {"total": row.total, "filled": row.filled}

        avg_result = await db.execute(
            select(GridOrder.grid_id, func.avg(GridOrder.price).label("avg_price"))
            .where(GridOrder.grid_id.in_(grid_ids), GridOrder.side == OrderSide.BUY)
            .group_by(GridOrder.grid_id)
        )
        for row in avg_result.all():
            avg_prices[row.grid_id] = float(row.avg_price) if row.avg_price else 0.0

    positions: list[PositionSummary] = []
    for g in grids:
        stats = order_stats.get(g.id, {"total": 0, "filled": 0})
        positions.append(PositionSummary(
            grid_id=str(g.id), grid_name=g.name, symbol=g.symbol,
            strategy=g.strategy.value, status=g.status.value, mode=g.mode.value,
            side="long", entry_price=avg_prices.get(g.id, 0.0),
            current_levels=stats["total"], filled_orders=stats["filled"],
            realized_pnl=float(g.realized_pnl), total_trades=g.total_trades,
            auto_convert_to=g.auto_convert_to, unconverted_pnl=float(g.unconverted_pnl or 0),
        ))

    equity_curve: list[dict] = []
    cumulative = 0.0
    for g in sorted(grids, key=lambda x: x.created_at):
        cumulative += float(g.realized_pnl)
        equity_curve.append({
            "date": g.created_at.isoformat() if g.created_at else "",
            "value": round(cumulative, 2),
            "label": g.name,
        })

    return DashboardResponse(
        total_grids=total_grids, active_grids=active_grids,
        total_pnl=round(total_pnl, 2), total_trades=total_trades,
        win_rate=round(win_rate, 1), strategies=strategies,
        positions=positions, equity_curve=equity_curve,
    )


# ─── Аналитика ───

class PnlPoint(BaseModel):
    date: str
    pnl: float
    cumulative: float


class GridPnlSeries(BaseModel):
    grid_id: str
    grid_name: str
    symbol: str
    strategy: str
    points: list[PnlPoint]


class DailyActivity(BaseModel):
    date: str
    trades: int
    buys: int
    sells: int


class GridDailyActivity(BaseModel):
    grid_id: str
    grid_name: str
    symbol: str
    days: list[DailyActivity]


class PeriodStats(BaseModel):
    pnl_24h: float
    pnl_today: float
    pnl_week: float
    pnl_month: float
    trades_24h: int
    trades_today: int
    trades_week: int
    trades_month: int
    total_loss: float
    total_profit: float
    best_trade: float
    worst_trade: float
    avg_profit_per_trade: float
    profit_factor: float
    win_rate: float
    total_volume: float
    max_drawdown: float
    avg_trade_pnl: float
    win_streak: int
    loss_streak: int
    max_win_streak: int
    max_loss_streak: int
    total_commission: float  # estimated commission paid
    total_rounds: int  # completed buy→sell cycles


class HourlyDistribution(BaseModel):
    hour: int
    trades: int
    pnl: float


class GridComparison(BaseModel):
    grid_id: str
    grid_name: str
    symbol: str
    strategy: str
    status: str
    total_trades: int
    realized_pnl: float
    win_rate: float
    avg_profit: float
    max_drawdown: float
    profit_factor: float
    total_volume: float
    runtime_hours: float
    total_commission: float
    total_rounds: int
    pnl_per_hour: float


class DrawdownPoint(BaseModel):
    date: str
    drawdown: float
    peak: float


class RecentTrade(BaseModel):
    grid_id: str
    grid_name: str
    symbol: str
    event_type: str
    side: str | None
    price: float | None
    amount: float | None
    pnl_delta: float | None
    commission: float | None
    created_at: str


class GridAnalytics(BaseModel):
    grid_id: str
    grid_name: str
    symbol: str
    strategy: str
    status: str
    period_stats: PeriodStats
    daily_activity: list[DailyActivity]
    hourly_distribution: list[HourlyDistribution]
    pnl_series: list[PnlPoint]
    drawdown_curve: list[DrawdownPoint]
    recent_trades: list[RecentTrade]


class AnalyticsResponse(BaseModel):
    # Per-grid analytics
    grids: list[GridAnalytics]
    # Aggregated across all grids
    total_stats: PeriodStats
    total_daily_activity: list[DailyActivity]
    grid_comparison: list[GridComparison]
    # Legacy fields for backward compat
    pnl_series: list[GridPnlSeries]
    daily_activity: list[DailyActivity]
    period_stats: PeriodStats
    recent_trades: list[RecentTrade]
    hourly_distribution: list[HourlyDistribution]
    drawdown_curve: list[DrawdownPoint]


def _empty_period_stats() -> PeriodStats:
    return PeriodStats(
        pnl_24h=0, pnl_today=0, pnl_week=0, pnl_month=0,
        trades_24h=0, trades_today=0, trades_week=0, trades_month=0,
        total_loss=0, total_profit=0, best_trade=0, worst_trade=0,
        avg_profit_per_trade=0, profit_factor=0, win_rate=0,
        total_volume=0, max_drawdown=0, avg_trade_pnl=0,
        win_streak=0, loss_streak=0, max_win_streak=0, max_loss_streak=0,
        total_commission=0, total_rounds=0,
    )


def _estimate_commission(price: Decimal, amount: Decimal, fee_rate: float = 0.001) -> float:
    """Estimate commission for one side of a trade."""
    return float(price) * float(amount) * fee_rate


def _compute_stats(
    orders: list,
    grids_map: dict,
    now: datetime,
    fee_rate: float = 0.001,
) -> tuple[PeriodStats, list[DrawdownPoint]]:
    """Compute period stats + drawdown from a list of filled GridOrder objects."""
    h24_start = now - timedelta(hours=24)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    month_start = today_start - timedelta(days=30)

    pnl_24h = pnl_today = pnl_week = pnl_month = 0.0
    trades_24h = trades_today = trades_week = trades_month = 0
    total_loss = total_profit = best_trade = worst_trade = 0.0
    total_volume = total_commission = 0.0
    winning_trades = losing_trades = total_rounds = 0

    cumulative_pnl = peak_pnl = max_drawdown = 0.0
    drawdown_curve: list[DrawdownPoint] = []
    current_win_streak = current_loss_streak = max_win_streak = max_loss_streak = 0
    hourly_map: dict[int, dict] = {h: {"trades": 0, "pnl": 0.0} for h in range(24)}

    for o in orders:
        delta = float(o.profit or 0)
        price_val = float(o.price or 0)
        amount_val = float(o.amount or 0)
        volume = amount_val * price_val
        total_volume += volume

        # Commission: fee on both buy and sell legs
        commission = _estimate_commission(o.price or Decimal(0), o.amount or Decimal(0), fee_rate) * 2
        total_commission += commission

        # Rounds: sell with positive profit = completed cycle
        if o.side == OrderSide.SELL and delta > 0:
            total_rounds += 1

        ts = o.filled_at or o.created_at

        if delta > 0:
            total_profit += delta
            winning_trades += 1
            current_win_streak += 1
            current_loss_streak = 0
            if current_win_streak > max_win_streak:
                max_win_streak = current_win_streak
        elif delta < 0:
            total_loss += delta
            losing_trades += 1
            current_loss_streak += 1
            current_win_streak = 0
            if current_loss_streak > max_loss_streak:
                max_loss_streak = current_loss_streak

        if delta > best_trade:
            best_trade = delta
        if delta < worst_trade:
            worst_trade = delta

        cumulative_pnl += delta
        if cumulative_pnl > peak_pnl:
            peak_pnl = cumulative_pnl
        dd = cumulative_pnl - peak_pnl
        if dd < max_drawdown:
            max_drawdown = dd
        drawdown_curve.append(DrawdownPoint(
            date=ts.isoformat(), drawdown=round(dd, 8), peak=round(peak_pnl, 8),
        ))

        # Считаем только завершённые циклы (sell с profit) как "trade"
        is_completed_trade = o.side == OrderSide.SELL and delta > 0
        if ts >= h24_start:
            pnl_24h += delta
            if is_completed_trade:
                trades_24h += 1
        if ts >= today_start:
            pnl_today += delta
            if is_completed_trade:
                trades_today += 1
        if ts >= week_start:
            pnl_week += delta
            if is_completed_trade:
                trades_week += 1
        if ts >= month_start:
            pnl_month += delta
            if is_completed_trade:
                trades_month += 1

        hour = ts.hour
        hourly_map[hour]["trades"] += 1
        hourly_map[hour]["pnl"] += delta

    avg_profit_per_trade = (total_profit / winning_trades) if winning_trades > 0 else 0.0
    profit_factor = (total_profit / abs(total_loss)) if total_loss != 0 else (999.0 if total_profit > 0 else 0.0)
    win_rate = (winning_trades / total_rounds * 100) if total_rounds > 0 else 0.0
    avg_trade_pnl = ((total_profit + total_loss) / total_rounds) if total_rounds > 0 else 0.0

    stats = PeriodStats(
        pnl_24h=round(pnl_24h, 8), pnl_today=round(pnl_today, 8),
        pnl_week=round(pnl_week, 8), pnl_month=round(pnl_month, 8),
        trades_24h=trades_24h, trades_today=trades_today,
        trades_week=trades_week, trades_month=trades_month,
        total_loss=round(total_loss, 8), total_profit=round(total_profit, 8),
        best_trade=round(best_trade, 8), worst_trade=round(worst_trade, 8),
        avg_profit_per_trade=round(avg_profit_per_trade, 8),
        profit_factor=round(profit_factor, 4), win_rate=round(win_rate, 1),
        total_volume=round(total_volume, 2), max_drawdown=round(max_drawdown, 8),
        avg_trade_pnl=round(avg_trade_pnl, 8),
        win_streak=current_win_streak, loss_streak=current_loss_streak,
        max_win_streak=max_win_streak, max_loss_streak=max_loss_streak,
        total_commission=round(total_commission, 8), total_rounds=total_rounds,
    )
    return stats, drawdown_curve


def _compute_daily_activity(orders: list) -> list[DailyActivity]:
    day_map: dict[str, DailyActivity] = {}
    for o in orders:
        d = (o.filled_at or o.created_at).strftime("%Y-%m-%d")
        if d not in day_map:
            day_map[d] = DailyActivity(date=d, trades=0, buys=0, sells=0)
        day_map[d].trades += 1
        if o.side == OrderSide.BUY:
            day_map[d].buys += 1
        elif o.side == OrderSide.SELL:
            day_map[d].sells += 1
    return sorted(day_map.values(), key=lambda x: x.date)


def _compute_hourly(orders: list) -> list[HourlyDistribution]:
    hourly_map: dict[int, dict] = {h: {"trades": 0, "pnl": 0.0} for h in range(24)}
    for o in orders:
        ts = o.filled_at or o.created_at
        hour = ts.hour
        hourly_map[hour]["trades"] += 1
        hourly_map[hour]["pnl"] += float(o.profit or 0)
    return [HourlyDistribution(hour=h, trades=d["trades"], pnl=round(d["pnl"], 8)) for h, d in sorted(hourly_map.items())]


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(require_role(UserRole.VIEWER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsResponse:
    now = datetime.now(UTC)
    since = now - timedelta(days=days)

    grid_query = (
        select(Grid)
        .join(ExchangeAccount, ExchangeAccount.id == Grid.account_id)
    )
    if current_user.role == UserRole.ADMIN:
        grid_query = grid_query.where(ExchangeAccount.owner_id == current_user.id)
    grid_result = await db.execute(grid_query)
    grids = {g.id: g for g in grid_result.scalars().all()}
    grid_ids = list(grids.keys())

    if not grid_ids:
        empty = _empty_period_stats()
        return AnalyticsResponse(
            grids=[], total_stats=empty, total_daily_activity=[],
            grid_comparison=[], pnl_series=[], daily_activity=[],
            period_stats=empty, recent_trades=[],
            hourly_distribution=[HourlyDistribution(hour=h, trades=0, pnl=0) for h in range(24)],
            drawdown_curve=[],
        )

    # Trade events for PnL series
    events_result = await db.execute(
        select(TradeEvent)
        .where(TradeEvent.grid_id.in_(grid_ids), TradeEvent.created_at >= since)
        .order_by(TradeEvent.created_at.asc())
    )
    events = list(events_result.scalars().all())

    # Filled orders — the source of truth for all metrics
    filled_orders_result = await db.execute(
        select(GridOrder)
        .where(
            GridOrder.grid_id.in_(grid_ids),
            GridOrder.status == OrderStatus.FILLED,
            GridOrder.filled_at >= since,
        )
        .order_by(GridOrder.filled_at.asc())
    )
    all_filled = list(filled_orders_result.scalars().all())

    # Group filled orders by grid
    grid_orders_map: dict[str, list] = {}
    for o in all_filled:
        grid_orders_map.setdefault(o.grid_id, []).append(o)

    # ─── PnL series from trade events ───
    grid_events: dict[str, list[TradeEvent]] = {}
    for e in events:
        grid_events.setdefault(str(e.grid_id), []).append(e)

    pnl_series: list[GridPnlSeries] = []
    for gid_str, evts in grid_events.items():
        g = grids.get(evts[0].grid_id)
        if not g:
            continue
        points: list[PnlPoint] = []
        cumulative = 0.0
        for e in evts:
            delta = float(e.pnl_delta or 0)
            cumulative += delta
            points.append(PnlPoint(date=e.created_at.isoformat(), pnl=round(delta, 8), cumulative=round(cumulative, 8)))
        if points:
            pnl_series.append(GridPnlSeries(
                grid_id=gid_str, grid_name=g.name, symbol=g.symbol,
                strategy=g.strategy.value, points=points,
            ))

    # ─── Per-grid analytics ───
    per_grid_analytics: list[GridAnalytics] = []
    for grid_id, g in grids.items():
        g_orders = grid_orders_map.get(grid_id, [])
        g_stats, g_dd = _compute_stats(g_orders, grids, now)
        g_daily = _compute_daily_activity(g_orders)
        g_hourly = _compute_hourly(g_orders)

        # PnL points for this grid
        g_pnl_points: list[PnlPoint] = []
        cum = 0.0
        for o in g_orders:
            delta = float(o.profit or 0)
            cum += delta
            g_pnl_points.append(PnlPoint(
                date=(o.filled_at or o.created_at).isoformat(),
                pnl=round(delta, 8), cumulative=round(cum, 8),
            ))

        # Recent trades for this grid
        g_recent: list[RecentTrade] = []
        for o in reversed(g_orders[-30:]):
            price_val = float(o.price or 0)
            amount_val = float(o.amount or 0)
            commission = price_val * amount_val * 0.001 * 2
            g_recent.append(RecentTrade(
                grid_id=str(grid_id), grid_name=g.name, symbol=g.symbol,
                event_type="filled", side=o.side.value if o.side else None,
                price=price_val if price_val else None,
                amount=amount_val if amount_val else None,
                pnl_delta=float(o.profit) if o.profit else None,
                commission=round(commission, 8),
                created_at=(o.filled_at or o.created_at).isoformat(),
            ))

        per_grid_analytics.append(GridAnalytics(
            grid_id=str(grid_id), grid_name=g.name, symbol=g.symbol,
            strategy=g.strategy.value, status=g.status.value,
            period_stats=g_stats, daily_activity=g_daily,
            hourly_distribution=g_hourly, pnl_series=g_pnl_points,
            drawdown_curve=g_dd, recent_trades=g_recent,
        ))

    # ─── Aggregated totals ───
    total_stats, total_dd = _compute_stats(all_filled, grids, now)
    total_daily = _compute_daily_activity(all_filled)
    total_hourly = _compute_hourly(all_filled)

    # ─── Grid comparison ───
    grid_comparison: list[GridComparison] = []
    for grid_id, g in grids.items():
        g_orders = grid_orders_map.get(grid_id, [])
        g_profit = sum(float(o.profit or 0) for o in g_orders if float(o.profit or 0) > 0)
        g_loss = sum(float(o.profit or 0) for o in g_orders if float(o.profit or 0) < 0)
        g_wins = sum(1 for o in g_orders if float(o.profit or 0) > 0)
        g_total = len(g_orders)
        g_volume = sum(float(o.amount or 0) * float(o.price or 0) for o in g_orders)
        g_commission = sum(float(o.amount or 0) * float(o.price or 0) * 0.001 * 2 for o in g_orders)
        g_rounds = sum(1 for o in g_orders if o.side == OrderSide.SELL and float(o.profit or 0) > 0)

        g_cum = g_peak = g_max_dd = 0.0
        for o in g_orders:
            g_cum += float(o.profit or 0)
            if g_cum > g_peak:
                g_peak = g_cum
            dd = g_cum - g_peak
            if dd < g_max_dd:
                g_max_dd = dd

        started = g.started_at or g.created_at
        stopped = g.stopped_at or now
        runtime_hours = (stopped - started).total_seconds() / 3600 if started else 0.0
        pnl_per_hour = float(g.realized_pnl) / runtime_hours if runtime_hours > 0 else 0.0

        grid_comparison.append(GridComparison(
            grid_id=str(grid_id), grid_name=g.name, symbol=g.symbol,
            strategy=g.strategy.value, status=g.status.value,
            total_trades=g_rounds,
            realized_pnl=round(float(g.realized_pnl), 8),
            win_rate=round(g_wins / g_total * 100, 1) if g_total > 0 else 0.0,
            avg_profit=round(g_profit / g_wins, 8) if g_wins > 0 else 0.0,
            max_drawdown=round(g_max_dd, 8),
            profit_factor=round(g_profit / abs(g_loss), 4) if g_loss != 0 else 999.0,
            total_volume=round(g_volume, 2),
            runtime_hours=round(runtime_hours, 1),
            total_commission=round(g_commission, 8),
            total_rounds=g_rounds,
            pnl_per_hour=round(pnl_per_hour, 8),
        ))

    # ─── Recent trades (all grids, last 30) ───
    recent_trades: list[RecentTrade] = []
    for o in reversed(all_filled[-30:]):
        g = grids.get(o.grid_id)
        price_val = float(o.price or 0)
        amount_val = float(o.amount or 0)
        commission = price_val * amount_val * 0.001 * 2
        recent_trades.append(RecentTrade(
            grid_id=str(o.grid_id), grid_name=g.name if g else "—", symbol=g.symbol if g else "—",
            event_type="filled", side=o.side.value if o.side else None,
            price=price_val if price_val else None,
            amount=amount_val if amount_val else None,
            pnl_delta=float(o.profit) if o.profit else None,
            commission=round(commission, 8),
            created_at=(o.filled_at or o.created_at).isoformat(),
        ))

    return AnalyticsResponse(
        grids=per_grid_analytics,
        total_stats=total_stats,
        total_daily_activity=total_daily,
        grid_comparison=grid_comparison,
        # Legacy compat
        pnl_series=pnl_series,
        daily_activity=total_daily,
        period_stats=total_stats,
        recent_trades=recent_trades,
        hourly_distribution=total_hourly,
        drawdown_curve=total_dd,
    )
