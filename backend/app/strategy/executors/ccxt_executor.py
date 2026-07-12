"""Универсальный live executor через ccxt с обработкой ошибок Binance/Bybit."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from decimal import Decimal
from functools import wraps
from typing import Any, TypeVar

import uuid

import ccxt.async_support as ccxt

from app.config import get_settings
from app.core.logging import get_logger
from app.models.enums import OrderSide, OrderStatus
from app.strategy.base_executor import BaseExecutor
from app.strategy.types import Balance, OrderResult, Ticker

log = get_logger("strategy.ccxt_executor")

T = TypeVar("T")

SUPPORTED_EXCHANGES = ("binance", "bybit")

# Binance error codes that warrant a retry
BINANCE_RETRY_CODES = {
    -1003,  # TOO_MANY_REQUESTS — rate limit
    -1015,  # TOO_MANY_ORDERS — order rate limit
    -1021,  # TIMESTAMP_OUTSIDE_RECV_WINDOW — clock sync issue
}
# Binance codes that are permanent failures
BINANCE_PERMANENT_CODES = {
    -1022,  # INVALID_SIGNATURE
    -2010,  # NEW_ORDER_REJECTED
    -2011,  # CANCEL_REJECTED
    -2013,  # NO_SUCH_ORDER
    -2015,  # INVALID_API_KEY
}

# Bybit error codes that warrant a retry
BYBIT_RETRY_CODES = {
    10006,  # rate limit
    10016,  # server error
    10018,  # service unavailable
}
BYBIT_PERMANENT_CODES = {
    10001,  # parameter error
    10002,  # invalid request
    10003,  # invalid api key
    10004,  # sign error
    110001,  # order not exists
    110007,  # insufficient balance
    110012,  # insufficient available balance
    110017,  # reduce only order failed
}


def _extract_error_code(exc: ccxt.ExchangeError) -> int | None:
    """Извлекаем числовой код из сообщения биржи."""
    msg = str(exc)
    # Binance: {"code":-1003,"msg":"..."}
    # Bybit: {"retCode":10006,"retMsg":"..."}
    for prefix in ('"code":', '"retCode":'):
        idx = msg.find(prefix)
        if idx != -1:
            start = idx + len(prefix)
            end = start
            while end < len(msg) and (msg[end].isdigit() or msg[end] == "-"):
                end += 1
            if end > start:
                try:
                    return int(msg[start:end])
                except ValueError:
                    pass
    return None


def _is_retryable(exc: Exception, exchange_id: str) -> bool:
    """Определяем, стоит ли повторять запрос."""
    if isinstance(exc, ccxt.RateLimitExceeded):
        return True
    if isinstance(exc, ccxt.NetworkError):
        return True
    if isinstance(exc, ccxt.ExchangeNotAvailable):
        return True
    if isinstance(exc, ccxt.RequestTimeout):
        return True
    if isinstance(exc, asyncio.TimeoutError):
        return True
    if isinstance(exc, ccxt.ExchangeError):
        code = _extract_error_code(exc)
        if code is not None:
            retry_codes = BINANCE_RETRY_CODES if exchange_id == "binance" else BYBIT_RETRY_CODES
            return code in retry_codes
    # Proxy/connection errors (SOCKS proxy down, DNS, etc.)
    if isinstance(exc, (OSError, ConnectionError)):
        return True
    msg = str(exc).lower()
    if "connection refused" in msg or "connect call failed" in msg or "proxy" in msg:
        return True
    return False


def retry_with_backoff(exchange_id_attr: str = "exchange_id", max_retries: int = 3, base_delay: float = 0.3):
    """Retry с экспоненциальной задержкой для retryable ошибок."""

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            self = args[0] if args else None
            ex_id = getattr(self, exchange_id_attr, "unknown") if self else "unknown"
            last_exception: Exception | None = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    last_exception = exc
                    if not _is_retryable(exc, ex_id) or attempt >= max_retries - 1:
                        break
                    delay = base_delay * (2**attempt)
                    log.warning(
                        "ccxt.retry",
                        exchange=ex_id,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay=delay,
                        error=str(exc)[:200],
                    )
                    await asyncio.sleep(delay)
            assert last_exception is not None
            raise last_exception

        return wrapper

    return decorator


class CcxtExecutor(BaseExecutor):
    """Исполнитель ордеров через ccxt для Binance и Bybit."""

    def __init__(
        self,
        exchange_id: str,
        api_key: str,
        api_secret: str,
        *,
        testnet: bool = True,
        symbol: str = "BTC/USDT",
    ) -> None:
        exchange_id = exchange_id.lower()
        if exchange_id not in SUPPORTED_EXCHANGES:
            raise ValueError(f"Unsupported exchange: {exchange_id}")

        exchange_class = getattr(ccxt, exchange_id)
        self.exchange_id = exchange_id
        self.symbol = symbol

        options: dict[str, Any] = {"defaultType": "spot"}
        if exchange_id == "binance":
            options["recvWindow"] = 5000
            options["adjustForTimeDifference"] = True

        config: dict[str, Any] = {
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "timeout": 10000,
            "options": options,
        }
        socks_proxy = get_settings().SOCKS_PROXY
        if socks_proxy:
            config["socksProxy"] = socks_proxy

        self.exchange = exchange_class(config)
        if testnet and hasattr(self.exchange, "set_sandbox_mode"):
            self.exchange.set_sandbox_mode(True)

        self.testnet = testnet
        self.grid_id: uuid.UUID | None = None  # set by grid_service for API tracking

        # TTL-кэш: снижает кол-во запросов к бирже
        self._ticker_cache: Ticker | None = None
        self._ticker_cache_ts: float = 0.0
        self._ticker_ttl: float = 1.0  # секунда

        self._open_orders_cache: list[dict[str, str]] | None = None
        self._open_orders_cache_ts: float = 0.0
        self._open_orders_ttl: float = 2.0  # секунды

        log.info(
            "ccxt_executor.initialized",
            exchange=self.exchange_id,
            testnet=self.testnet,
            symbol=self.symbol,
        )

    def _record_api_call(self) -> None:
        """Record an API call for rate tracking."""
        if self.grid_id is not None:
            from app.core.grid_activity_logger import get_api_counter
            get_api_counter(self.grid_id).record()

    @retry_with_backoff()
    async def get_ticker(self) -> Ticker:
        now = time.monotonic()
        if self._ticker_cache is not None and (now - self._ticker_cache_ts) < self._ticker_ttl:
            return self._ticker_cache
        self._record_api_call()
        ticker = await self.exchange.fetch_ticker(self.symbol)
        bid = Decimal(str(ticker.get("bid") or ticker.get("last") or 0))
        ask = Decimal(str(ticker.get("ask") or ticker.get("last") or 0))
        result = Ticker(bid=bid, ask=ask)
        self._ticker_cache = result
        self._ticker_cache_ts = now
        return result

    @retry_with_backoff()
    async def get_balance(self) -> Balance:
        self._record_api_call()
        balance = await self.exchange.fetch_balance()
        base, quote = self.symbol.split("/", maxsplit=1)
        free = balance.get("free", {})
        return Balance(
            base=Decimal(str(free.get(base, 0))),
            quote=Decimal(str(free.get(quote, 0))),
        )

    @retry_with_backoff()
    async def place_order(self, side: OrderSide, price: Decimal, amount: Decimal) -> OrderResult:
        log.info(
            "ccxt_executor.place_order",
            exchange=self.exchange_id,
            symbol=self.symbol,
            side=side.value,
            price=str(price),
            amount=str(amount),
        )
        try:
            self._record_api_call()
            order = await self.exchange.create_limit_order(
                self.symbol,
                side.value,
                float(amount),
                float(price),
                params={"timeInForce": "GTC"},
            )
            self._open_orders_cache = None  # инвалидируем кэш
            return OrderResult(exchange_order_id=str(order["id"]), success=True)
        except ccxt.InsufficientFunds:
            log.warning("ccxt_executor.insufficient_funds", exchange=self.exchange_id, symbol=self.symbol)
            return OrderResult(exchange_order_id="", success=False, error="insufficient_funds")
        except ccxt.InvalidOrder as exc:
            code = _extract_error_code(exc)
            log.warning(
                "ccxt_executor.invalid_order",
                exchange=self.exchange_id,
                symbol=self.symbol,
                code=code,
                error=str(exc)[:200],
            )
            return OrderResult(exchange_order_id="", success=False, error=f"invalid_order:{code or 'unknown'}")
        except ccxt.ExchangeError as exc:
            code = _extract_error_code(exc)
            # Permanent failures should not be retried
            permanent = BINANCE_PERMANENT_CODES if self.exchange_id == "binance" else BYBIT_PERMANENT_CODES
            if code is not None and code in permanent:
                log.error(
                    "ccxt_executor.permanent_error",
                    exchange=self.exchange_id,
                    code=code,
                    error=str(exc)[:200],
                )
                return OrderResult(exchange_order_id="", success=False, error=f"permanent:{code}")
            # Otherwise re-raise for retry decorator
            raise

    @retry_with_backoff()
    async def cancel_order(self, exchange_order_id: str) -> bool:
        log.info(
            "ccxt_executor.cancel_order",
            exchange=self.exchange_id,
            symbol=self.symbol,
            order_id=exchange_order_id,
        )
        try:
            self._record_api_call()
            await self.exchange.cancel_order(exchange_order_id, self.symbol)
            self._open_orders_cache = None  # инвалидируем кэш
            return True
        except ccxt.OrderNotFound:
            log.warning(
                "ccxt_executor.cancel_order_not_found",
                exchange=self.exchange_id,
                order_id=exchange_order_id,
            )
            return False
        except ccxt.ExchangeError as exc:
            code = _extract_error_code(exc)
            permanent = BINANCE_PERMANENT_CODES if self.exchange_id == "binance" else BYBIT_PERMANENT_CODES
            if code is not None and code in permanent:
                log.error(
                    "ccxt_executor.cancel_permanent_error",
                    exchange=self.exchange_id,
                    order_id=exchange_order_id,
                    code=code,
                )
                return False
            raise

    @retry_with_backoff()
    async def get_order_status(self, exchange_order_id: str) -> OrderStatus:
        self._record_api_call()
        try:
            params: dict[str, Any] = {}
            # Bybit: suppress "not in last 500 orders" warning
            if self.exchange_id == "bybit":
                params["acknowledged"] = True
            order = await self.exchange.fetch_order(exchange_order_id, self.symbol, params=params)
        except ccxt.OrderNotFound:
            # Ордер не найден — проверяем через open_orders, может был исполнен
            log.warning(
                "ccxt_executor.order_not_found",
                exchange=self.exchange_id,
                order_id=exchange_order_id,
            )
            return OrderStatus.CANCELLED
        except ccxt.ExchangeError as exc:
            code = _extract_error_code(exc)
            error_msg = str(exc).lower()
            # Bybit "not in last 500 orders" — пробуем через trades
            if "last 500 orders" in error_msg or "not found" in error_msg:
                try:
                    trades = await self.exchange.fetch_my_trades(self.symbol, limit=50)
                    for trade in trades:
                        if str(trade.get("order", "")) == exchange_order_id:
                            return OrderStatus.FILLED
                except Exception:
                    pass
                return OrderStatus.CANCELLED
            log.error(
                "ccxt_executor.order_status_failed",
                exchange=self.exchange_id,
                order_id=exchange_order_id,
                code=code,
                error=str(exc)[:200],
            )
            return OrderStatus.ERROR

        status = str(order.get("status", "")).lower()
        mapping = {
            "open": OrderStatus.PLACED,
            "closed": OrderStatus.FILLED,
            "canceled": OrderStatus.CANCELLED,
            "cancelled": OrderStatus.CANCELLED,
        }
        return mapping.get(status, OrderStatus.ERROR)

    @retry_with_backoff()
    async def get_open_orders(self) -> list[dict[str, str]] | None:
        """Возвращает список открытых ордеров или None при ошибке.

        ВАЖНО: None означает что запрос не удался — нельзя считать что ордеров нет.
        Пустой [] означает что ордеров действительно нет.
        """
        now = time.monotonic()
        if self._open_orders_cache is not None and (now - self._open_orders_cache_ts) < self._open_orders_ttl:
            return self._open_orders_cache
        try:
            self._record_api_call()
            orders = await self.exchange.fetch_open_orders(self.symbol)
        except ccxt.ExchangeError as exc:
            log.error(
                "ccxt_executor.open_orders_failed",
                exchange=self.exchange_id,
                symbol=self.symbol,
                error=str(exc)[:200],
            )
            return None

        result = [
            {
                "id": str(order.get("id", "")),
                "side": str(order.get("side", "")).lower(),
                "price": str(order.get("price", "")),
                "amount": str(order.get("amount", "")),
                "status": str(order.get("status", "")).lower(),
            }
            for order in orders
        ]
        self._open_orders_cache = result
        self._open_orders_cache_ts = now
        return result

    async def close(self) -> None:
        try:
            await self.exchange.close()
        except Exception:
            pass
