"""Базовый интерфейс исполнителей ордеров."""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from app.models.enums import OrderSide, OrderStatus
from app.strategy.types import Balance, OrderResult, Ticker


class BaseExecutor(ABC):
    @abstractmethod
    async def get_ticker(self) -> Ticker: ...

    @abstractmethod
    async def get_balance(self) -> Balance: ...

    @abstractmethod
    async def place_order(self, side: OrderSide, price: Decimal, amount: Decimal) -> OrderResult: ...

    @abstractmethod
    async def cancel_order(self, exchange_order_id: str) -> bool: ...

    @abstractmethod
    async def get_order_status(self, exchange_order_id: str) -> OrderStatus: ...

    @abstractmethod
    async def get_open_orders(self) -> list[dict[str, str]] | None: ...

    async def get_filled_order_ids(self, exchange_order_ids: list[str]) -> set[str]:
        """Вернуть ID ордеров, которые исполнены. Batch-оптимизация для rate limits.

        По умолчанию — через get_open_orders (1 запрос вместо N).
        """
        open_orders = await self.get_open_orders()
        if open_orders is None:
            return set()  # Ошибка — не считаем ничего исполненным
        open_ids = {o["id"] for o in open_orders}
        return {oid for oid in exchange_order_ids if oid and oid not in open_ids}
