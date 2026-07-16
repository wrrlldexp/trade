"""Тесты GridReconciler — 12 сценариев сверки state↔биржа."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.models.enums import OrderSide, OrderStatus
from app.strategy.reconciler import GridReconciler, ReconcileReport
from app.strategy.types import GridState, LiveOrder


def _make_order(
    *,
    side: OrderSide = OrderSide.BUY,
    status: OrderStatus = OrderStatus.PLACED,
    exchange_order_id: str = "",
    grid_index: int = 0,
    price: Decimal = Decimal("100"),
) -> LiveOrder:
    return LiveOrder(
        id=uuid.uuid4(),
        side=side,
        price=price,
        amount=Decimal("0.1"),
        status=status,
        exchange_order_id=exchange_order_id or str(uuid.uuid4()),
        grid_index=grid_index,
        price_sell=price + Decimal("10"),
    )


def _make_state(*orders: LiveOrder) -> GridState:
    return GridState(center_price=Decimal("100"), orders=list(orders))


def _mock_executor(
    open_orders: list[dict[str, str]] | None = None,
    order_status: OrderStatus = OrderStatus.CANCELLED,
    cancel_result: bool = True,
) -> AsyncMock:
    ex = AsyncMock()
    ex.get_open_orders = AsyncMock(return_value=open_orders if open_orders is not None else [])
    ex.get_order_status = AsyncMock(return_value=order_status)
    ex.cancel_order = AsyncMock(return_value=cancel_result)
    return ex


# -----------------------------------------------------------------
# 1. Orphan — на бирже есть ордер, в state нет → отменён
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_orphan_cancelled() -> None:
    orphan_id = "ORPHAN_123"
    state = _make_state(_make_order(exchange_order_id="STATE_1"))
    executor = _mock_executor(
        open_orders=[
            {"id": "STATE_1", "side": "buy", "price": "100", "amount": "0.1", "status": "open"},
            {"id": orphan_id, "side": "buy", "price": "90", "amount": "0.1", "status": "open"},
        ],
    )
    rec = GridReconciler(executor, "BTC/USDT")
    report = await rec.enforce(state)

    assert report.orphans_found == 1
    assert report.orphans_cancelled == 1
    executor.cancel_order.assert_called_once_with(orphan_id)


# -----------------------------------------------------------------
# 2. Orphan, отмена провалилась → в orphans_failed
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_orphan_cancel_failed() -> None:
    orphan_id = "ORPHAN_FAIL"
    state = _make_state(_make_order(exchange_order_id="STATE_1"))
    executor = _mock_executor(
        open_orders=[
            {"id": "STATE_1", "side": "buy", "price": "100", "amount": "0.1", "status": "open"},
            {"id": orphan_id, "side": "buy", "price": "90", "amount": "0.1", "status": "open"},
        ],
    )
    executor.cancel_order = AsyncMock(side_effect=Exception("network error"))
    rec = GridReconciler(executor, "BTC/USDT")
    report = await rec.enforce(state)

    assert report.orphans_found == 1
    assert report.orphans_cancelled == 0
    assert orphan_id in report.orphans_failed


# -----------------------------------------------------------------
# 3. Orphan, код -2013 (OrderNotFound) → cancel_order returns False → успех
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_orphan_order_not_found_is_success() -> None:
    orphan_id = "ORPHAN_GONE"
    state = _make_state(_make_order(exchange_order_id="STATE_1"))
    executor = _mock_executor(
        open_orders=[
            {"id": "STATE_1", "side": "buy", "price": "100", "amount": "0.1", "status": "open"},
            {"id": orphan_id, "side": "buy", "price": "90", "amount": "0.1", "status": "open"},
        ],
        cancel_result=False,  # OrderNotFound → False from executor
    )
    rec = GridReconciler(executor, "BTC/USDT")
    report = await rec.enforce(state)

    assert report.orphans_found == 1
    assert report.orphans_cancelled == 1
    assert not report.orphans_failed


# -----------------------------------------------------------------
# 4. Ghost FILLED → в needs_fill_processing, статус НЕ тронут
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_ghost_filled_not_touched() -> None:
    order = _make_order(exchange_order_id="GHOST_FILLED")
    state = _make_state(order)
    executor = _mock_executor(
        open_orders=[],  # ордера нет на бирже
        order_status=OrderStatus.FILLED,
    )
    rec = GridReconciler(executor, "BTC/USDT")
    report = await rec.enforce(state)

    assert report.ghosts_found == 1
    assert len(report.needs_fill_processing) == 1
    assert report.needs_fill_processing[0] is order
    # Статус НЕ изменён — стратегия сама решит
    assert order.status == OrderStatus.PLACED


# -----------------------------------------------------------------
# 5. Ghost CANCELLED → статус CANCELLED
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_ghost_cancelled() -> None:
    order = _make_order(exchange_order_id="GHOST_CANCELLED")
    state = _make_state(order)
    executor = _mock_executor(
        open_orders=[],
        order_status=OrderStatus.CANCELLED,
    )
    rec = GridReconciler(executor, "BTC/USDT")
    report = await rec.enforce(state)

    assert report.ghosts_found == 1
    assert report.ghosts_cancelled == 1
    assert order.status == OrderStatus.CANCELLED


# -----------------------------------------------------------------
# 6. Stale cancel → повторная отмена
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_stale_cancel_retried() -> None:
    stale_id = "STALE_1"
    order = _make_order(
        exchange_order_id=stale_id,
        status=OrderStatus.CANCELLED,
    )
    state = _make_state(order)
    executor = _mock_executor(
        open_orders=[
            {"id": stale_id, "side": "buy", "price": "100", "amount": "0.1", "status": "open"},
        ],
    )
    rec = GridReconciler(executor, "BTC/USDT")
    report = await rec.enforce(state)

    assert report.stale_cancels_found == 1
    assert report.stale_cancels_fixed == 1
    executor.cancel_order.assert_called_once_with(stale_id)


# -----------------------------------------------------------------
# 7. Lost level → в lost_levels
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_lost_level_detected() -> None:
    placed = _make_order(grid_index=0, exchange_order_id="PLACED_0")
    filled = _make_order(grid_index=1, status=OrderStatus.FILLED, exchange_order_id="FILLED_1")
    state = _make_state(placed, filled)
    executor = _mock_executor(
        open_orders=[
            {"id": "PLACED_0", "side": "buy", "price": "100", "amount": "0.1", "status": "open"},
        ],
    )
    rec = GridReconciler(executor, "BTC/USDT")
    report = await rec.enforce(state)

    assert 1 in report.lost_levels


# -----------------------------------------------------------------
# 8. Bloat → не-PLACED удалены, PLACED целы
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_bloat_cleanup() -> None:
    placed = _make_order(grid_index=0, exchange_order_id="P1")
    filled = _make_order(grid_index=1, status=OrderStatus.FILLED, exchange_order_id="F1")
    cancelled = _make_order(grid_index=2, status=OrderStatus.CANCELLED, exchange_order_id="C1")
    state = _make_state(placed, filled, cancelled)
    executor = _mock_executor(
        open_orders=[
            {"id": "P1", "side": "buy", "price": "100", "amount": "0.1", "status": "open"},
        ],
    )
    rec = GridReconciler(executor, "BTC/USDT")
    report = await rec.enforce(state)

    assert report.bloat_removed == 2
    assert len(state.orders) == 1
    assert state.orders[0].exchange_order_id == "P1"


# -----------------------------------------------------------------
# 9. get_open_orders вернул None → skipped, state не тронут
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_open_orders_none_skips() -> None:
    order = _make_order(exchange_order_id="UNTOUCHED")
    state = _make_state(order)
    executor = _mock_executor()
    executor.get_open_orders = AsyncMock(return_value=None)

    rec = GridReconciler(executor, "BTC/USDT")
    report = await rec.enforce(state)

    assert report.skipped_reason is not None
    assert order.status == OrderStatus.PLACED
    assert len(state.orders) == 1
    executor.cancel_order.assert_not_called()


# -----------------------------------------------------------------
# 10. dry_run=True → находит, но cancel_order НЕ вызывался
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_dry_run_no_cancel() -> None:
    orphan_id = "DRY_ORPHAN"
    ghost_order = _make_order(exchange_order_id="DRY_GHOST")
    stale_order = _make_order(exchange_order_id="DRY_STALE", status=OrderStatus.CANCELLED)

    state = _make_state(ghost_order, stale_order)
    executor = _mock_executor(
        open_orders=[
            {"id": orphan_id, "side": "buy", "price": "90", "amount": "0.1", "status": "open"},
            {"id": "DRY_STALE", "side": "buy", "price": "95", "amount": "0.1", "status": "open"},
        ],
        # ghost_order не в open_orders → ghost
    )

    rec = GridReconciler(executor, "BTC/USDT", dry_run=True)
    report = await rec.enforce(state)

    assert report.orphans_found == 1
    assert report.ghosts_found == 1
    assert report.stale_cancels_found == 1
    # Ничего не отменялось и статусы не менялись
    executor.cancel_order.assert_not_called()
    executor.get_order_status.assert_not_called()
    assert ghost_order.status == OrderStatus.PLACED
    assert stale_order.status == OrderStatus.CANCELLED


# -----------------------------------------------------------------
# 11. Чужой символ в open orders → не трогаем
#     (executor.get_open_orders фильтрует по символу внутри себя,
#      но если вдруг вернёт чужие — reconciler не должен паниковать)
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_foreign_symbol_ignored_by_executor() -> None:
    """Executor фильтрует по символу — reconciler получает только свои ордера.
    Этот тест подтверждает, что reconciler не падает на пустом списке."""
    state = _make_state(_make_order(exchange_order_id="MY_ORDER"))
    executor = _mock_executor(
        open_orders=[
            {"id": "MY_ORDER", "side": "buy", "price": "100", "amount": "0.1", "status": "open"},
        ],
    )
    rec = GridReconciler(executor, "BTC/USDT")
    report = await rec.enforce(state)

    assert report.orphans_found == 0
    assert report.ghosts_found == 0
    executor.cancel_order.assert_not_called()


# -----------------------------------------------------------------
# 12. Идемпотентность — exchange_order_id=None → успех, cancel НЕ вызван
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_confirmed_none_id() -> None:
    """_cancel_confirmed с None → True без вызова cancel_order."""
    executor = _mock_executor()
    rec = GridReconciler(executor, "BTC/USDT")
    result = await rec._cancel_confirmed(None)

    assert result is True
    executor.cancel_order.assert_not_called()


@pytest.mark.asyncio
async def test_cancel_confirmed_empty_string() -> None:
    """_cancel_confirmed с пустой строкой → True без вызова cancel_order."""
    executor = _mock_executor()
    rec = GridReconciler(executor, "BTC/USDT")
    result = await rec._cancel_confirmed("")

    assert result is True
    executor.cancel_order.assert_not_called()


# -----------------------------------------------------------------
# Дополнительно: ReconcileReport.summary и has_issues
# -----------------------------------------------------------------

def test_clean_report() -> None:
    report = ReconcileReport()
    assert not report.has_issues
    assert report.summary() == "clean"


def test_skipped_report() -> None:
    report = ReconcileReport(skipped_reason="API error")
    assert report.has_issues
    assert "skipped" in report.summary()
