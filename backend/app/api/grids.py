"""Grids API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import log_action
from app.core.deps import require_role
from app.db import get_db
from app.models import (
    BotLog,
    ExchangeAccount,
    Grid,
    GridActivityLog,
    GridAnalyticsSession,
    GridStatus,
    OrderStatus,
    TradeEvent,
    User,
    UserRole,
)
from app.schemas.common import GridOrderResponse, GridResponse, TradeEventResponse
from app.schemas.grid import GridCreate, GridDetailResponse, GridUpdate
from app.services.grid_service import start_grid, stop_grid

router = APIRouter()


async def _get_grid(db: AsyncSession, user: User, grid_id: UUID) -> Grid:
    query = (
        select(Grid)
        .join(ExchangeAccount, ExchangeAccount.id == Grid.account_id)
        .where(Grid.id == grid_id)
        .options(selectinload(Grid.orders), selectinload(Grid.account))
    )
    if user.role == UserRole.ADMIN:
        query = query.where(ExchangeAccount.owner_id == user.id)
    result = await db.execute(query)
    grid = result.scalar_one_or_none()
    if grid is None:
        raise HTTPException(status_code=404, detail="Grid not found")
    return grid


@router.get("/", response_model=list[GridResponse])
async def list_grids(
    current_user: User = Depends(require_role(UserRole.VIEWER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[GridResponse]:
    query = (
        select(Grid)
        .join(ExchangeAccount, ExchangeAccount.id == Grid.account_id)
        .order_by(Grid.created_at.desc())
    )
    if current_user.role == UserRole.ADMIN:
        query = query.where(ExchangeAccount.owner_id == current_user.id)
    result = await db.execute(query)
    return [GridResponse.model_validate(item) for item in result.scalars().all()]


@router.post("/", response_model=GridResponse)
async def create_grid(
    payload: GridCreate,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> GridResponse:
    account_result = await db.execute(
        select(ExchangeAccount).where(
            ExchangeAccount.id == payload.account_id,
            ExchangeAccount.owner_id == current_user.id,
        )
    )
    if account_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Account not found")

    grid = Grid(
        account_id=payload.account_id,
        created_by_id=current_user.id,
        name=payload.name,
        symbol=payload.symbol,
        mode=payload.mode,
        strategy=payload.strategy,
        lot_size=payload.lot_size,
        lot_quote=payload.lot_quote,
        profit_step=payload.profit_step,
        grid_step=payload.grid_step,
        levels_above=payload.levels_above,
        levels_below=payload.levels_below,
        rebuild_timeout_sec=payload.rebuild_timeout_sec,
        adaptive_timer_sec=payload.adaptive_timer_sec,
        auto_convert_to=payload.auto_convert_to,
    )
    db.add(grid)
    await db.flush()
    await log_action(db, current_user.id, "grid.create", entity_type="grid", entity_id=str(grid.id), request=request)
    return GridResponse.model_validate(grid)


@router.get("/{grid_id}", response_model=GridDetailResponse)
async def get_grid(
    grid_id: UUID,
    current_user: User = Depends(require_role(UserRole.VIEWER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> GridDetailResponse:
    grid = await _get_grid(db, current_user, grid_id)
    return GridDetailResponse(
        **GridResponse.model_validate(grid).model_dump(),
        orders=[GridOrderResponse.model_validate(order) for order in grid.orders],
    )


_SETTINGS_SNAPSHOT_FIELDS = [
    "strategy", "lot_size", "lot_quote", "profit_step", "grid_step",
    "levels_above", "levels_below", "rebuild_timeout_sec", "adaptive_timer_sec",
    "auto_convert_to",
]


def _snapshot_settings(grid: Grid) -> dict:
    """Снэпшот текущих настроек сетки для аналитики."""
    return {
        field: str(getattr(grid, field)) if hasattr(getattr(grid, field), "quantize") else getattr(grid, field)
        for field in _SETTINGS_SNAPSHOT_FIELDS
    }


# Параметры, которые можно менять на работающей сетке
# (не влияют на структуру ордеров, применяются на следующем тике)
_HOT_UPDATE_FIELDS = {
    "name", "lot_size", "lot_quote", "profit_step", "rebuild_timeout_sec",
    "adaptive_timer_sec", "auto_convert_to",
}


@router.patch("/{grid_id}", response_model=GridResponse)
async def update_grid(
    grid_id: UUID,
    payload: GridUpdate,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> GridResponse:
    grid = await _get_grid(db, current_user, grid_id)
    changes = payload.model_dump(exclude_none=True)

    if grid.status == GridStatus.RUNNING:
        # На работающей сетке разрешены только безопасные параметры
        blocked = set(changes.keys()) - _HOT_UPDATE_FIELDS
        if blocked:
            raise HTTPException(
                status_code=400,
                detail=f"Остановите сетку для изменения: {', '.join(blocked)}",
            )

    # Снэпшот ДО изменений
    before = _snapshot_settings(grid)

    for field, value in changes.items():
        setattr(grid, field, value)

    # Снэпшот ПОСЛЕ изменений
    after = _snapshot_settings(grid)

    # Создаём 24-часовую сессию аналитики если настройки реально изменились
    if before != after:
        now = datetime.now(UTC)
        session = GridAnalyticsSession(
            grid_id=grid.id,
            user_id=current_user.id,
            started_at=now,
            expires_at=now + timedelta(hours=24),
            settings_before=before,
            settings_after=after,
        )
        db.add(session)

    await log_action(db, current_user.id, "grid.update", entity_type="grid", entity_id=str(grid.id), request=request)
    return GridResponse.model_validate(grid)


@router.post("/{grid_id}/start", response_model=GridResponse)
async def run_grid(
    grid_id: UUID,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> GridResponse:
    await _get_grid(db, current_user, grid_id)
    try:
        grid = await start_grid(db, grid_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await log_action(db, current_user.id, "grid.start", entity_type="grid", entity_id=str(grid.id), request=request)
    return GridResponse.model_validate(grid)


@router.post("/{grid_id}/stop", response_model=GridResponse)
async def halt_grid(
    grid_id: UUID,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> GridResponse:
    await _get_grid(db, current_user, grid_id)
    grid = await stop_grid(db, grid_id)
    await log_action(db, current_user.id, "grid.stop", entity_type="grid", entity_id=str(grid.id), request=request)
    return GridResponse.model_validate(grid)


@router.delete("/{grid_id}")
async def delete_grid(
    grid_id: UUID,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    grid = await _get_grid(db, current_user, grid_id)
    if grid.status == GridStatus.RUNNING:
        await stop_grid(db, grid_id)

    # Отменяем зависшие ордера на бирже (если stop_grid не снял)
    placed_orders = [o for o in grid.orders if o.status == OrderStatus.PLACED and o.exchange_order_id]
    if placed_orders:
        try:
            executor = grid.account.to_executor(paper_mode=False, symbol=grid.symbol)
            for order in placed_orders:
                try:
                    await executor.cancel_order(order.exchange_order_id)
                except Exception:
                    pass  # ордер мог уже исполниться/отмениться
            close = getattr(executor, "close", None)
            if callable(close):
                await close()
        except Exception:
            pass  # не блокируем удаление из-за биржи

    await db.delete(grid)
    await log_action(db, current_user.id, "grid.delete", entity_type="grid", entity_id=str(grid.id), request=request)
    return {"success": True}


@router.get("/{grid_id}/events", response_model=list[TradeEventResponse])
async def grid_events(
    grid_id: UUID,
    current_user: User = Depends(require_role(UserRole.VIEWER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[TradeEventResponse]:
    await _get_grid(db, current_user, grid_id)
    result = await db.execute(select(TradeEvent).where(TradeEvent.grid_id == grid_id).order_by(TradeEvent.created_at.desc()).limit(50))
    return [TradeEventResponse.model_validate(item) for item in result.scalars().all()]


@router.get("/{grid_id}/orders", response_model=list[GridOrderResponse])
async def grid_orders(
    grid_id: UUID,
    current_user: User = Depends(require_role(UserRole.VIEWER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[GridOrderResponse]:
    grid = await _get_grid(db, current_user, grid_id)
    return [GridOrderResponse.model_validate(item) for item in grid.orders]


# ------------------------------------------------------------------
# Аналитические сессии (24ч после изменения настроек)
# ------------------------------------------------------------------


@router.get("/{grid_id}/analytics-sessions")
async def list_analytics_sessions(
    grid_id: UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Список аналитических сессий для сетки."""
    await _get_grid(db, current_user, grid_id)
    result = await db.execute(
        select(GridAnalyticsSession)
        .where(GridAnalyticsSession.grid_id == grid_id)
        .order_by(GridAnalyticsSession.started_at.desc())
        .limit(50)
    )
    sessions = result.scalars().all()
    now = datetime.now(UTC)
    return [
        {
            "id": s.id,
            "started_at": s.started_at.isoformat(),
            "expires_at": s.expires_at.isoformat(),
            "is_active": now < s.expires_at,
            "settings_before": s.settings_before,
            "settings_after": s.settings_after,
        }
        for s in sessions
    ]


@router.get("/{grid_id}/analytics-sessions/{session_id}")
async def get_analytics_session_data(
    grid_id: UUID,
    session_id: int,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Трейды и логи за период аналитической сессии (24ч)."""
    await _get_grid(db, current_user, grid_id)

    result = await db.execute(
        select(GridAnalyticsSession).where(
            GridAnalyticsSession.id == session_id,
            GridAnalyticsSession.grid_id == grid_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Analytics session not found")

    # Трейды за период сессии
    trades_result = await db.execute(
        select(TradeEvent)
        .where(
            TradeEvent.grid_id == grid_id,
            TradeEvent.created_at >= session.started_at,
            TradeEvent.created_at <= session.expires_at,
        )
        .order_by(TradeEvent.created_at)
    )
    trades = trades_result.scalars().all()

    # Логи за период сессии
    logs_result = await db.execute(
        select(BotLog)
        .where(
            BotLog.grid_id == grid_id,
            BotLog.created_at >= session.started_at,
            BotLog.created_at <= session.expires_at,
        )
        .order_by(BotLog.created_at)
    )
    logs = logs_result.scalars().all()

    total_pnl = sum((t.pnl_delta or 0) for t in trades)

    return {
        "session": {
            "id": session.id,
            "started_at": session.started_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "is_active": datetime.now(UTC) < session.expires_at,
            "settings_before": session.settings_before,
            "settings_after": session.settings_after,
        },
        "summary": {
            "total_trades": len(trades),
            "total_pnl": str(total_pnl),
            "total_logs": len(logs),
            "errors": sum(1 for l in logs if l.level.value in ("error", "critical")),
        },
        "trades": [
            {
                "id": t.id,
                "event_type": t.event_type.value,
                "price": str(t.price) if t.price else None,
                "pnl_delta": str(t.pnl_delta) if t.pnl_delta else None,
                "payload": t.payload,
                "created_at": t.created_at.isoformat(),
            }
            for t in trades
        ],
        "logs": [
            {
                "id": l.id,
                "level": l.level.value,
                "message": l.message,
                "source": l.source,
                "traceback": l.traceback,
                "payload": l.payload,
                "created_at": l.created_at.isoformat(),
            }
            for l in logs
        ],
    }


@router.get("/{grid_id}/activity")
async def get_grid_activity(
    grid_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.ULTRAADMIN)),
    event: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """Детальный лог активности сетки — тики, fill-ы, перестроения, API-статистика."""
    await _get_grid(db, user, grid_id)  # проверка доступа

    query = (
        select(GridActivityLog)
        .where(GridActivityLog.grid_id == grid_id)
        .order_by(GridActivityLog.created_at.desc())
    )
    if event:
        query = query.where(GridActivityLog.event == event)
    query = query.offset(offset).limit(min(limit, 500))

    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        {
            "id": log.id,
            "event": log.event,
            "data": log.data,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
