"""Paper executor без сети."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.models.enums import OrderSide, OrderStatus
from app.strategy.executor import Executor
from app.strategy.types import Balance, LiveOrder, OrderResult, Ticker


@dataclass(slots=True)
class PaperOrder:
    exchange_order_id: str
    side: OrderSide
    price: Decimal
    amount: Decimal
    status: OrderStatus = OrderStatus.PLACED


class PaperExecutor(Executor):
    def __init__(
        self,
        *,
        initial_base: Decimal = Decimal("0"),
        initial_quote: Decimal = Decimal("100000"),
        bid: Decimal = Decimal("50000"),
        ask: Decimal = Decimal("50001"),
    ) -> None:
        self.balance = Balance(base=initial_base, quote=initial_quote)
        self._ticker = Ticker(bid=bid, ask=ask)
        self._counter = 0
        self.orders: dict[str, PaperOrder] = {}
        self.filled_order_ids: list[str] = []

    def seed_open_orders(self, live_orders: list[LiveOrder]) -> None:
        self.orders = {
            order.exchange_order_id: PaperOrder(
                exchange_order_id=order.exchange_order_id,
                side=order.side,
                price=order.price,
                amount=order.amount,
                status=order.status,
            )
            for order in live_orders
            if order.exchange_order_id
        }
        paper_ids = [
            int(order.exchange_order_id.removeprefix("paper-"))
            for order in live_orders
            if order.exchange_order_id.startswith("paper-")
        ]
        self._counter = max(paper_ids, default=self._counter)

    async def set_ticker(self, bid: Decimal, ask: Decimal) -> list[str]:
        self._ticker = Ticker(bid=bid, ask=ask)
        return await self._process_orders()

    async def _process_orders(self) -> list[str]:
        filled_ids: list[str] = []
        for order in list(self.orders.values()):
            if order.status != OrderStatus.PLACED:
                continue
            if order.side == OrderSide.BUY and self._ticker.ask <= order.price:
                self.balance.base += order.amount
                self.balance.quote -= order.price * order.amount
                order.status = OrderStatus.FILLED
                filled_ids.append(order.exchange_order_id)
            elif order.side == OrderSide.SELL and self._ticker.bid >= order.price:
                self.balance.base -= order.amount
                self.balance.quote += order.price * order.amount
                order.status = OrderStatus.FILLED
                filled_ids.append(order.exchange_order_id)

        self.filled_order_ids.extend(filled_ids)
        return filled_ids

    async def get_ticker(self) -> Ticker:
        return self._ticker

    async def get_balance(self) -> Balance:
        return self.balance

    async def place_order(self, side: OrderSide, price: Decimal, amount: Decimal) -> OrderResult:
        self._counter += 1
        order_id = f"paper-{self._counter}"
        self.orders[order_id] = PaperOrder(order_id, side, price, amount)
        await self._process_orders()
        return OrderResult(exchange_order_id=order_id, success=True)

    async def cancel_order(self, exchange_order_id: str) -> bool:
        order = self.orders.get(exchange_order_id)
        if order is None or order.status == OrderStatus.FILLED:
            return False
        order.status = OrderStatus.CANCELLED
        return True

    async def get_order_status(self, exchange_order_id: str) -> OrderStatus:
        order = self.orders.get(exchange_order_id)
        if order is None:
            return OrderStatus.ERROR
        return order.status

    async def get_filled_order_ids(self, exchange_order_ids: list[str]) -> set[str]:
        return {
            oid
            for oid in exchange_order_ids
            if oid in self.orders and self.orders[oid].status == OrderStatus.FILLED
        }

    async def get_open_orders(self) -> list[dict[str, str]] | None:
        return [
            {
                "id": order.exchange_order_id,
                "side": order.side.value,
                "price": str(order.price),
                "amount": str(order.amount),
                "status": order.status.value,
            }
            for order in self.orders.values()
            if order.status == OrderStatus.PLACED
        ]
