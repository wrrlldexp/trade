"""Ядро торговых стратегий — все 6 режимов из legacy MoneyBot v1."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from decimal import ROUND_DOWN, Decimal

from app.models.enums import OrderSide, OrderStatus, StrategyType
from app.strategy.executor import Executor
from app.strategy.types import GridParams, GridState, LiveOrder, Ticker

# Точность для BTC-подобных сумм (8 знаков)
_PREC = Decimal("0.00000001")


def _trunc8(value: Decimal) -> Decimal:
    """Обрезать до 8 знаков (как в legacy: intval(x * 10^8) / 10^8)."""
    return value.quantize(_PREC, rounding=ROUND_DOWN)


class GridEngine:
    """Единый движок для всех стратегий."""

    def __init__(self, params: GridParams, executor: Executor):
        self.params = params
        self.executor = executor

    # ------------------------------------------------------------------
    # Построение начальной сетки
    # ------------------------------------------------------------------

    async def build_initial_grid(self, center_price: Decimal) -> GridState:
        """Раскладывает сетку от min до max с шагом grid_step и маржой profit_step."""
        orders: list[LiveOrder] = []
        idx = 0

        # Получаем баланс один раз, чтобы не ставить ордера на которые нет средств
        balance = await self.executor.get_balance()
        available_base = balance.base
        available_quote = balance.quote

        for level in range(1, self.params.levels_below + 1):
            price_buy = center_price - (self.params.grid_step * Decimal(level))
            price_sell = price_buy + self.params.profit_step
            if price_buy <= 0:
                continue
            lot = self._calc_lot(price_buy)
            cost = _trunc8(lot * price_buy)
            if cost > available_quote:
                continue
            order = await self._place_grid_order(
                OrderSide.BUY, price_buy, price_sell, idx,
            )
            if order is not None:
                orders.append(order)
                available_quote -= cost
            idx += 1
        for level in range(1, self.params.levels_above + 1):
            price_sell = center_price + (self.params.grid_step * Decimal(level))
            price_buy = price_sell - self.params.profit_step
            if price_sell <= 0:
                continue
            lot = self._calc_lot(price_sell)
            if lot > available_base:
                continue
            order = await self._place_grid_order(
                OrderSide.SELL, price_buy, price_sell, idx,
            )
            if order is not None:
                orders.append(order)
                available_base -= lot
            idx += 1
        if not orders:
            raise ValueError(
                "Невозможно построить сетку: все уровни имеют нулевую или отрицательную цену. "
                "Уменьшите grid_step или количество уровней."
            )
        return GridState(center_price=center_price, orders=orders)

    def _calc_lot(self, price: Decimal) -> Decimal:
        """Рассчитать размер лота. Если lot_quote задан — пересчёт по цене."""
        if self.params.lot_quote and price > 0:
            return _trunc8(self.params.lot_quote / price)
        return self.params.lot_size

    async def _place_grid_order(
        self,
        side: OrderSide,
        price_buy: Decimal,
        price_sell: Decimal,
        grid_index: int,
        amount: Decimal | None = None,
    ) -> LiveOrder | None:
        """Размещает ордер на бирже. Возвращает None если биржа отклонила."""
        price = price_buy if side == OrderSide.BUY else price_sell
        lot = amount if amount is not None else self._calc_lot(price)
        # Throttle: пауза перед запросом к бирже, чтобы не превышать rate limit
        await asyncio.sleep(0.15)
        result = await self.executor.place_order(side, price, lot)
        if not result.success:
            return None
        return LiveOrder(
            id=uuid.uuid4(),
            side=side,
            price=price_buy,
            price_sell=price_sell,
            amount=lot,
            status=OrderStatus.PLACED,
            exchange_order_id=result.exchange_order_id,
            grid_index=grid_index,
        )

    # ------------------------------------------------------------------
    # Свойства стратегии
    # ------------------------------------------------------------------

    @property
    def _is_adaptive(self) -> bool:
        return self.params.strategy in (StrategyType.ADAPTIVE, StrategyType.ADAPTIVE_CAPITALIZATION)

    @property
    def _is_capitalization(self) -> bool:
        return self.params.strategy in (
            StrategyType.CAPITALIZATION,
            StrategyType.REVERSE_CAPITALIZATION,
            StrategyType.ADAPTIVE_CAPITALIZATION,
        )

    @property
    def _is_reverse(self) -> bool:
        return self.params.strategy in (StrategyType.REVERSE, StrategyType.REVERSE_CAPITALIZATION)

    # ------------------------------------------------------------------
    # Обработка исполнения ордера (on_order_filled) — ядро legacy orderCheck
    # ------------------------------------------------------------------

    async def on_order_filled(
        self,
        state: GridState,
        filled_order: LiveOrder,
        filled_amount: Decimal | None = None,
    ) -> GridState:
        """Обрабатывает исполненный ордер в зависимости от стратегии."""
        # Помечаем ордер как filled
        for order in state.orders:
            if order.exchange_order_id == filled_order.exchange_order_id:
                order.status = OrderStatus.FILLED
                order.filled_at = filled_order.filled_at
                break

        order_amount = filled_amount if filled_amount is not None else filled_order.amount
        strategy = self.params.strategy

        if filled_order.side == OrderSide.BUY:
            # Купили → продаём
            state = await self._handle_buy_filled(state, filled_order, order_amount, strategy)
        else:
            # Продали → покупаем
            state = await self._handle_sell_filled(state, filled_order, order_amount, strategy)

        return state

    async def _handle_buy_filled(
        self,
        state: GridState,
        order: LiveOrder,
        order_amount: Decimal,
        strategy: StrategyType,
    ) -> GridState:
        """Купили → ставим ордер на продажу (или перекупку для адаптивных)."""
        if strategy in (StrategyType.SIMPLE, StrategyType.CAPITALIZATION, StrategyType.REVERSE):
            # Стратегии 1, 2, 3: продаём по price_sell с amount
            new_order = await self._flip_order(order, OrderSide.SELL, order.price_sell, order.amount)
            if new_order is not None:
                state.orders.append(new_order)

        elif strategy == StrategyType.REVERSE_CAPITALIZATION:
            # Стратегия 4: продаём по price_sell с базовым лотом (не выросшим)
            sell_lot = self._calc_lot(order.price)
            new_order = await self._flip_order(order, OrderSide.SELL, order.price_sell, sell_lot)
            if new_order is not None:
                state.orders.append(new_order)

        elif self._is_adaptive:
            # Стратегии 5, 6 — как простая: продаём по price_sell с пересчётом лота
            sell_lot = self._calc_lot(order.price_sell)
            new_order = await self._flip_order(order, OrderSide.SELL, order.price_sell, sell_lot)
            if new_order is not None:
                state.orders.append(new_order)

        return state

    async def _handle_sell_filled(
        self,
        state: GridState,
        order: LiveOrder,
        order_amount: Decimal,
        strategy: StrategyType,
    ) -> GridState:
        """Продали → ставим ордер на покупку."""
        current_profit = self._calc_profit(order, order_amount)

        if strategy == StrategyType.SIMPLE:
            # Стратегия 1: покупаем по price с пересчётом лота (фиатный лот → стабильный расход USDT)
            buy_amount = self._calc_lot(order.price)
            new_order = await self._flip_order(order, OrderSide.BUY, order.price, buy_amount)
            if new_order is not None:
                new_order.profit = order.profit + current_profit
                new_order.count_complete = order.count_complete + 1
                state.orders.append(new_order)
                state.total_trades += 1
                state.realized_pnl += current_profit

        elif strategy == StrategyType.CAPITALIZATION:
            # Стратегия 2: полная реинвестиция — CSV-логика
            # sell_total = amount × price_sell (получили USDT с продажи)
            # fee = sell_total × fee × 2 (комиссия обеих ног)
            # next_volume = sell_total − fee (чистый объём для реинвестирования)
            # new_amount = next_volume / price_buy (конвертируем обратно в крипту)
            sell_total = order.amount * order.price_sell
            total_fee = _trunc8(sell_total * self.params.fee * Decimal(2))
            next_volume = _trunc8(sell_total - total_fee)
            volume_spent = order.amount * order.price
            current_profit = _trunc8(next_volume - volume_spent)
            new_amount = _trunc8(next_volume / order.price)

            new_order = await self._flip_order(order, OrderSide.BUY, order.price, new_amount)
            if new_order is not None:
                new_order.profit = order.profit + current_profit
                new_order.count_complete = order.count_complete + 1
                state.orders.append(new_order)
                state.total_trades += 1
                state.realized_pnl += current_profit

        elif strategy == StrategyType.REVERSE:
            # Стратегия 3: прибыль через price ratio
            new_amount = order.amount + current_profit
            new_order = await self._flip_order(order, OrderSide.BUY, order.price, new_amount)
            if new_order is not None:
                new_order.profit = order.profit + current_profit
                new_order.count_complete = order.count_complete + 1
                state.orders.append(new_order)
                state.total_trades += 1
                state.realized_pnl += current_profit

        elif strategy == StrategyType.REVERSE_CAPITALIZATION:
            # Стратегия 4: реверс + капитализация
            new_amount = _trunc8(order.amount + current_profit)
            new_order = await self._flip_order(order, OrderSide.BUY, order.price, new_amount)
            if new_order is not None:
                new_order.profit = order.profit + current_profit
                new_order.count_complete = order.count_complete + 1
                state.orders.append(new_order)
                state.total_trades += 1
                state.realized_pnl += current_profit

        elif strategy == StrategyType.ADAPTIVE:
            # Стратегия 5 — как простая: покупаем по price с пересчётом лота
            buy_lot = self._calc_lot(order.price)
            new_order = await self._flip_order(order, OrderSide.BUY, order.price, buy_lot)
            if new_order is not None:
                new_order.profit = order.profit + current_profit
                new_order.count_complete = order.count_complete + 1
                state.orders.append(new_order)
                state.total_trades += 1
                state.realized_pnl += current_profit

        elif strategy == StrategyType.ADAPTIVE_CAPITALIZATION:
            # Стратегия 6: как капитализация — реинвест прибыли в лот
            base_lot = self._calc_lot(order.price)
            new_lot = _trunc8(base_lot + (current_profit / order.price))
            new_order = await self._flip_order(order, OrderSide.BUY, order.price, new_lot)
            if new_order is not None:
                new_order.amount = new_lot
                new_order.profit = order.profit + current_profit
                new_order.count_complete = order.count_complete + 1
                state.orders.append(new_order)
                state.total_trades += 1
                state.realized_pnl += current_profit

        return state

    def _calc_profit(self, order: LiveOrder, order_amount: Decimal) -> Decimal:
        """Расчёт чистой прибыли от сделки (за вычетом комиссий buy + sell).

        Формула: g_net = trunc(q * profit_step - fee * q * (p_buy + p_sell))
        Для reverse: g_net_base = trunc(g_net_quote / p_buy)
        """
        fee = self.params.fee
        # Чистая прибыль в quote (USDT)
        gross_quote = order_amount * self.params.profit_step
        fee_cost = fee * order_amount * (order.price + order.price_sell)
        net_quote = _trunc8(gross_quote - fee_cost)
        if net_quote <= 0:
            return Decimal("0")
        if self._is_reverse:
            # Reverse: прибыль в base-валюте
            return _trunc8(net_quote / order.price)
        return net_quote

    async def _flip_order(
        self,
        source: LiveOrder,
        new_side: OrderSide,
        price: Decimal,
        amount: Decimal,
    ) -> LiveOrder | None:
        """Создаёт зеркальный ордер. Возвращает None если биржа отклонила."""
        result = await self.executor.place_order(new_side, price, amount)
        if not result.success:
            return None
        return LiveOrder(
            id=uuid.uuid4(),
            side=new_side,
            price=source.price,
            price_sell=source.price_sell,
            amount=amount,
            status=OrderStatus.PLACED,
            exchange_order_id=result.exchange_order_id,
            grid_index=source.grid_index,
        )

    # ------------------------------------------------------------------
    # Адаптивная подсетка — сдвиг (из legacy adaptive.php)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Адаптивный сдвиг — двигает ВСЮ сетку на дельту
    # ------------------------------------------------------------------

    async def shift_grid(self, state: GridState, current_price: Decimal) -> GridState:
        """Сдвигает всю сетку на дельту между текущей ценой и крайним ордером.

        Цена выше сетки → delta = цена - max(price_sell) → прибавляем ко всем
        Цена ниже сетки → delta = min(price) - цена → вычитаем из всех
        """
        placed = [o for o in state.orders if o.status == OrderStatus.PLACED]
        if not placed:
            return state

        max_sell = max(o.price_sell for o in placed)
        min_buy = min(o.price for o in placed)

        if current_price > max_sell:
            delta = current_price - max_sell
        elif current_price < min_buy:
            delta = -(min_buy - current_price)
        else:
            return state  # цена внутри сетки

        # Отменяем все placed ордера на бирже
        for order in placed:
            await asyncio.sleep(0.15)
            await self.executor.cancel_order(order.exchange_order_id)
            order.status = OrderStatus.CANCELLED

        # Ставим новые ордера со сдвинутыми ценами
        new_orders: list[LiveOrder] = []
        for order in placed:
            new_price = order.price + delta
            new_price_sell = order.price_sell + delta
            if new_price <= 0:
                continue
            lot = self._calc_lot(new_price)
            side = OrderSide.BUY if new_price < current_price else OrderSide.SELL
            new_order = await self._place_grid_order(
                side, new_price, new_price_sell, order.grid_index, lot,
            )
            if new_order is not None:
                new_orders.append(new_order)

        state.orders.extend(new_orders)
        state.last_boundary_hit_at = None
        return state

    # ------------------------------------------------------------------
    # Boundary & Rebuild
    # ------------------------------------------------------------------

    def check_boundary(self, state: GridState, current_price: Decimal, now: datetime) -> GridState:
        active_orders = [o for o in state.orders if o.status == OrderStatus.PLACED]
        if not active_orders:
            return state

        min_price = min(o.price for o in active_orders)
        max_price = max(o.price_sell for o in active_orders)
        outside = current_price < min_price or current_price > max_price

        if outside and state.last_boundary_hit_at is None:
            state.last_boundary_hit_at = now
        elif not outside and state.last_boundary_hit_at is not None:
            state.last_boundary_hit_at = None
        return state

    def should_rebuild(self, state: GridState, now: datetime) -> bool:
        if state.last_boundary_hit_at is None:
            return False
        return now - state.last_boundary_hit_at >= timedelta(seconds=self.params.rebuild_timeout_sec)

    async def rebuild_grid(self, state: GridState, new_center_price: Decimal) -> GridState:
        for order in state.orders:
            if order.status == OrderStatus.PLACED:
                await asyncio.sleep(0.15)
                await self.executor.cancel_order(order.exchange_order_id)
                order.status = OrderStatus.CANCELLED

        new_state = await self.build_initial_grid(new_center_price)
        new_state.realized_pnl = state.realized_pnl
        new_state.total_trades = state.total_trades
        new_state.last_boundary_hit_at = None
        return new_state

    # ------------------------------------------------------------------
    # Главный tick
    # ------------------------------------------------------------------

    async def tick(self, state: GridState, now: datetime) -> tuple[GridState, Ticker]:
        ticker = await self.executor.get_ticker()

        # Защита от некорректного тикера (bid/ask = 0 или спред > 5%)
        if ticker.bid <= 0 or ticker.ask <= 0:
            return state, ticker
        spread_pct = (ticker.ask - ticker.bid) / ticker.mid * Decimal("100")
        if spread_pct > Decimal("5"):
            return state, ticker  # Аномальный спред — пропускаем тик

        # Проверка fills — on_order_filled сам ставит зеркальный ордер (flip)
        placed_orders = [o for o in state.orders if o.status == OrderStatus.PLACED]
        placed_ids = [o.exchange_order_id for o in placed_orders]
        if placed_ids:
            # Один вызов get_open_orders для определения пропавших ордеров
            open_orders = await self.executor.get_open_orders()
            if open_orders is None:
                # Ошибка запроса — пропускаем тик, не трогаем ордера
                return state, ticker
            open_ids = {o["id"] for o in open_orders}
            missing_orders = [o for o in placed_orders if o.exchange_order_id not in open_ids]

            for order in missing_orders:
                # Верифицируем статус каждого пропавшего ордера через API биржи.
                # Это защита от ложных fills при рестарте: отменённый ордер тоже
                # отсутствует в open orders, но его не нужно "флипать".
                actual_status = await self.executor.get_order_status(order.exchange_order_id)
                if actual_status == OrderStatus.FILLED:
                    order.status = OrderStatus.FILLED
                    order.filled_at = now
                    state = await self.on_order_filled(state, order)
                elif actual_status == OrderStatus.CANCELLED:
                    order.status = OrderStatus.CANCELLED
                # ERROR — не трогаем, попробуем в следующем тике

        # Boundary check
        state = self.check_boundary(state, ticker.mid, now)
        if self.should_rebuild(state, now):
            if self._is_adaptive:
                # Адаптивная: сдвигаем всю сетку на дельту
                state = await self.shift_grid(state, ticker.mid)
            else:
                # Простые стратегии: полная перестройка
                state = await self.rebuild_grid(state, ticker.mid)

        return state, ticker
