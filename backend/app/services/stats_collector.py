"""Сбор статистики сеток. Аналог legacy cli/statistic.php.

НЕ содержит торговой логики. Только читает состояние и биржу.
Отдельный цикл с интервалом 60 секунд.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.models import Grid, GridStatus, OrderStatus
from app.models.stats import AccountStatSnapshot, GridStatSnapshot
from app.services.grid_service import registry

logger = logging.getLogger("stats_collector")


@dataclass
class StatsCollectReport:
    accounts_processed: int = 0
    grids_processed: int = 0
    grids_skipped: int = 0
    errors: list[str] = field(default_factory=list)


class GridStatsCollector:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        interval_sec: int = 60,
    ):
        self._session_factory = session_factory
        self._interval_sec = interval_sec
        # Аналог $oldNetAssets из legacy — предыдущий net_asset по account_id
        self._prev_net_assets: dict[uuid.UUID, Decimal] = {}

    async def collect_once(self) -> StatsCollectReport:
        """Один цикл сбора. Аналог тела while(true) из legacy."""
        report = StatsCollectReport()
        now = datetime.now(UTC)

        async with self._session_factory() as db:
            # Загружаем все RUNNING-сетки с аккаунтами
            result = await db.execute(
                select(Grid)
                .where(Grid.status == GridStatus.RUNNING)
                .options(selectinload(Grid.account))
            )
            grids = list(result.scalars().all())

            if not grids:
                return report

            # Шаг 1: Снимок баланса по КАЖДОМУ аккаунту (один раз на аккаунт)
            account_ids_seen: set[uuid.UUID] = set()
            account_net_assets: dict[uuid.UUID, Decimal] = {}
            account_balances: dict[uuid.UUID, tuple[Decimal, Decimal, Decimal]] = {}

            for grid in grids:
                aid = grid.account_id
                if aid in account_ids_seen:
                    continue
                account_ids_seen.add(aid)

                executor = registry.executors.get(grid.id)
                if executor is None:
                    continue

                try:
                    await asyncio.sleep(0.15)
                    ticker = await executor.get_ticker()
                    if ticker.mid <= 0:
                        report.errors.append(f"account {aid}: ticker mid=0")
                        continue

                    await asyncio.sleep(0.15)
                    # Используем exchange.fetch_balance() для получения total (free+used)
                    exchange = getattr(executor, "exchange", None)
                    if exchange is not None:
                        raw_balance = await exchange.fetch_balance()
                        base_sym, quote_sym = grid.symbol.split("/", maxsplit=1)
                        total = raw_balance.get("total", raw_balance.get("free", {}))
                        base_total = Decimal(str(total.get(base_sym, 0)))
                        quote_total = Decimal(str(total.get(quote_sym, 0)))
                    else:
                        # Paper mode — get_balance() возвращает всё (нет locked)
                        balance = await executor.get_balance()
                        base_total = balance.base
                        quote_total = balance.quote

                    net_asset = base_total * ticker.mid + quote_total

                    if net_asset <= 0:
                        report.errors.append(f"account {aid}: net_asset=0")
                        continue

                    account_net_assets[aid] = net_asset
                    account_balances[aid] = (base_total, quote_total, ticker.mid)

                    # Записываем AccountStatSnapshot
                    db.add(AccountStatSnapshot(
                        account_id=aid,
                        time=now,
                        net_asset=net_asset,
                        base_balance=base_total,
                        quote_balance=quote_total,
                        price=ticker.mid,
                    ))
                    report.accounts_processed += 1

                except Exception as exc:
                    report.errors.append(f"account {aid}: {exc!s:.200}")
                    continue

            # Шаг 2: По каждой активной сетке
            for grid in grids:
                aid = grid.account_id
                if aid not in account_net_assets:
                    report.grids_skipped += 1
                    continue

                try:
                    net_asset = account_net_assets[aid]
                    state = registry.states.get(grid.id)

                    # profit_math = state.realized_pnl (кумулятивный счётчик)
                    profit_math = state.realized_pnl if state else grid.realized_pnl
                    total_trades = state.total_trades if state else grid.total_trades
                    placed_count = (
                        sum(1 for o in state.orders if o.status == OrderStatus.PLACED)
                        if state else 0
                    )

                    # Курс
                    _, _, price = account_balances[aid]

                    # Первый замер — запоминаем net_asset
                    if aid not in self._prev_net_assets:
                        self._prev_net_assets[aid] = net_asset

                    # net_asset_sag = дельта с прошлого замера
                    prev = self._prev_net_assets[aid]
                    net_asset_sag = net_asset - prev

                    # profit_drift = расхождение расчёта с фактом
                    # Используем start_amount из БД (реальный стартовый объём)
                    start = grid.start_amount if grid.start_amount and grid.start_amount > 0 else net_asset
                    actual_gain = net_asset - start
                    profit_drift = profit_math - actual_gain

                    db.add(GridStatSnapshot(
                        grid_id=grid.id,
                        time=now,
                        course=price,
                        profit_math=profit_math,
                        net_asset=net_asset,
                        net_asset_sag=net_asset_sag,
                        profit_drift=profit_drift,
                        total_trades=total_trades,
                        placed_orders=placed_count,
                    ))
                    report.grids_processed += 1

                except Exception as exc:
                    report.errors.append(f"grid {grid.id}: {exc!s:.200}")
                    report.grids_skipped += 1
                    continue

            # Обновляем prev
            for aid, na in account_net_assets.items():
                self._prev_net_assets[aid] = na

            await db.commit()

        return report

    async def run_forever(self) -> None:
        """Цикл с интервалом. Аналог while(true) + sleep(60) из legacy."""
        logger.info("Stats collector started, interval=%ds", self._interval_sec)
        while True:
            try:
                report = await self.collect_once()
                if report.errors:
                    logger.warning(
                        "Stats: %d accounts, %d grids, %d skipped, errors: %s",
                        report.accounts_processed,
                        report.grids_processed,
                        report.grids_skipped,
                        report.errors[:3],
                    )
            except Exception:
                logger.exception("Stats collector cycle failed")
            await asyncio.sleep(self._interval_sec)
