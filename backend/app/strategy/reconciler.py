"""Слой контроля целостности сетки.

НЕ содержит торговой логики. Не знает про окна, авансы, дельты, лоты.
Единственная задача — привести state в соответствие с реальностью на бирже.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from app.models.enums import OrderStatus
from app.strategy.base_executor import BaseExecutor
from app.strategy.types import GridState, LiveOrder

logger = logging.getLogger("reconciler")


@dataclass
class ReconcileReport:
    orphans_found: int = 0
    orphans_cancelled: int = 0
    orphans_failed: list[str] = field(default_factory=list)

    ghosts_found: int = 0
    ghosts_cancelled: int = 0
    needs_fill_processing: list[LiveOrder] = field(default_factory=list)

    stale_cancels_found: int = 0
    stale_cancels_fixed: int = 0

    lost_levels: list[int] = field(default_factory=list)

    bloat_removed: int = 0

    skipped_reason: str | None = None

    @property
    def has_issues(self) -> bool:
        return (
            self.orphans_found > 0
            or self.ghosts_found > 0
            or self.stale_cancels_found > 0
            or len(self.lost_levels) > 0
            or self.bloat_removed > 0
            or self.skipped_reason is not None
        )

    def summary(self) -> str:
        """Однострочная сводка для лога."""
        if self.skipped_reason:
            return f"skipped: {self.skipped_reason}"
        parts: list[str] = []
        if self.orphans_found:
            parts.append(
                f"orphans={self.orphans_found} cancelled={self.orphans_cancelled}"
                + (f" failed={self.orphans_failed}" if self.orphans_failed else "")
            )
        if self.ghosts_found:
            fills = len(self.needs_fill_processing)
            parts.append(
                f"ghosts={self.ghosts_found} cancelled={self.ghosts_cancelled}"
                + (f" needs_fill={fills}" if fills else "")
            )
        if self.stale_cancels_found:
            parts.append(f"stale_cancels={self.stale_cancels_found} fixed={self.stale_cancels_fixed}")
        if self.lost_levels:
            parts.append(f"lost_levels={self.lost_levels}")
        if self.bloat_removed:
            parts.append(f"bloat_removed={self.bloat_removed}")
        return "; ".join(parts) if parts else "clean"


class GridReconciler:
    """Сверяет state с биржей и чинит расхождения.

    НЕ ставит новых ордеров. НЕ обрабатывает fill'ы. НЕ считает лоты и прибыль.
    """

    def __init__(
        self,
        executor: BaseExecutor,
        symbol: str,
        *,
        dry_run: bool = False,
    ):
        self._executor = executor
        self._symbol = symbol
        self._dry_run = dry_run

    async def enforce(self, state: GridState) -> ReconcileReport:
        """Полная сверка. Мутирует state (статусы, чистка). Возвращает отчёт."""
        report = ReconcileReport()

        # 1. Один запрос get_open_orders
        open_orders = await self._executor.get_open_orders()
        if open_orders is None:
            report.skipped_reason = "get_open_orders returned None (API error)"
            return report

        open_ids: set[str] = {o["id"] for o in open_orders}

        # 2. Stale cancels — CANCELLED в state, но ордер ещё жив на бирже
        await self._fix_stale_cancels(state, open_ids, report)

        # 3. Ghosts — PLACED в state, но на бирже нет
        await self._fix_ghosts(state, open_ids, report)

        # 4. Orphans — на бирже есть, а в state нет PLACED с таким id
        await self._fix_orphans(state, open_ids, report)

        # 5. Lost levels — grid_index без PLACED ордера
        self._detect_lost_levels(state, report)

        # 6. Bloat — чистка не-PLACED
        self._cleanup_bloat(state, report)

        return report

    # ------------------------------------------------------------------
    # Stale cancels
    # ------------------------------------------------------------------

    async def _fix_stale_cancels(
        self, state: GridState, open_ids: set[str], report: ReconcileReport,
    ) -> None:
        for order in state.orders:
            if order.status != OrderStatus.CANCELLED:
                continue
            if not order.exchange_order_id:
                continue
            if order.exchange_order_id not in open_ids:
                continue

            report.stale_cancels_found += 1
            if self._dry_run:
                continue

            ok = await self._cancel_confirmed(order.exchange_order_id)
            if ok:
                report.stale_cancels_fixed += 1

    # ------------------------------------------------------------------
    # Ghosts
    # ------------------------------------------------------------------

    async def _fix_ghosts(
        self, state: GridState, open_ids: set[str], report: ReconcileReport,
    ) -> None:
        for order in state.orders:
            if order.status != OrderStatus.PLACED:
                continue
            if order.exchange_order_id in open_ids:
                continue

            report.ghosts_found += 1
            if self._dry_run:
                continue

            await asyncio.sleep(0.15)
            actual = await self._executor.get_order_status(order.exchange_order_id)
            if actual == OrderStatus.FILLED:
                report.needs_fill_processing.append(order)
                # НЕ меняем статус — пусть стратегия решает
            elif actual in (OrderStatus.CANCELLED, OrderStatus.ERROR):
                order.status = OrderStatus.CANCELLED
                report.ghosts_cancelled += 1

    # ------------------------------------------------------------------
    # Orphans
    # ------------------------------------------------------------------

    async def _fix_orphans(
        self, state: GridState, open_ids: set[str], report: ReconcileReport,
    ) -> None:
        # exchange_order_id ВСЕХ ордеров в state (любой статус).
        # Сироты — это ордера, о которых state вообще не знает.
        # Stale cancels (CANCELLED но живые) обрабатываются отдельно.
        state_known_ids: set[str] = {
            o.exchange_order_id
            for o in state.orders
            if o.exchange_order_id
        }

        for oid in open_ids:
            if oid in state_known_ids:
                continue

            report.orphans_found += 1
            if self._dry_run:
                continue

            ok = await self._cancel_confirmed(oid)
            if ok:
                report.orphans_cancelled += 1
            else:
                report.orphans_failed.append(oid)

    # ------------------------------------------------------------------
    # Lost levels
    # ------------------------------------------------------------------

    def _detect_lost_levels(self, state: GridState, report: ReconcileReport) -> None:
        all_indices: set[int] = {o.grid_index for o in state.orders}
        placed_indices: set[int] = {
            o.grid_index for o in state.orders if o.status == OrderStatus.PLACED
        }
        lost = sorted(all_indices - placed_indices)
        if lost:
            report.lost_levels = lost

    # ------------------------------------------------------------------
    # Bloat cleanup
    # ------------------------------------------------------------------

    def _cleanup_bloat(self, state: GridState, report: ReconcileReport) -> None:
        if self._dry_run:
            not_placed = sum(1 for o in state.orders if o.status != OrderStatus.PLACED)
            report.bloat_removed = not_placed
            return

        before = len(state.orders)
        state.orders = [o for o in state.orders if o.status == OrderStatus.PLACED]
        report.bloat_removed = before - len(state.orders)

    # ------------------------------------------------------------------
    # Cancel confirmed — ядро надёжности
    # ------------------------------------------------------------------

    async def _cancel_confirmed(self, exchange_order_id: str | None) -> bool:
        """True только при подтверждении, что ордера на бирже нет.

        Механизм 1 — идемпотентность: нет id → нечего отменять → успех.
        Механизм 2 — cancel_order возвращает True (отменён) или False
                      (OrderNotFound / permanent error — ордера уже нет) → успех.
        Механизм 3 — exception (сетевой сбой, rate limit) → False,
                      статус НЕ меняется, ретрай на следующем цикле.
        """
        if not exchange_order_id:
            return True

        try:
            await asyncio.sleep(0.15)
            # cancel_order возвращает bool:
            # True  = отменён
            # False = OrderNotFound / permanent error (ордера уже нет на бирже)
            # Оба результата означают "ордера на бирже нет" → успех
            await self._executor.cancel_order(exchange_order_id)
            return True
        except Exception:
            # Сетевой сбой / rate limit / неизвестная ошибка
            # Статус не меняем — следующий цикл попробует снова
            logger.warning(
                "cancel_confirmed failed for %s, will retry next cycle",
                exchange_order_id,
                exc_info=True,
            )
            return False
