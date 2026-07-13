"""WebSocket stream manager — real-time order and ticker updates from exchange.

Uses ccxt's watch_orders() and watch_ticker() for instant event delivery.
Falls back gracefully if WS is unavailable (exchange continues via REST polling).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from decimal import Decimal
from typing import Any

import ccxt.pro as ccxtpro

from app.config import get_settings
from app.core.logging import get_logger
from app.models.enums import OrderSide, OrderStatus
from app.strategy.types import Ticker

log = get_logger("ws_stream")


class WsOrderEvent:
    """Parsed order event from WebSocket stream."""

    __slots__ = ("exchange_order_id", "status", "side", "price", "amount", "filled", "timestamp")

    def __init__(
        self,
        exchange_order_id: str,
        status: OrderStatus,
        side: OrderSide,
        price: Decimal,
        amount: Decimal,
        filled: Decimal,
        timestamp: float,
    ) -> None:
        self.exchange_order_id = exchange_order_id
        self.status = status
        self.side = side
        self.price = price
        self.amount = amount
        self.filled = filled
        self.timestamp = timestamp

    def __repr__(self) -> str:
        return f"WsOrderEvent({self.exchange_order_id}, {self.status.value}, {self.side.value}, {self.price})"


# Callback type: async function called on each order event
OrderEventCallback = Callable[[WsOrderEvent], Coroutine[Any, Any, None]]
TickerCallback = Callable[[Ticker], Coroutine[Any, Any, None]]


class ExchangeWsStream:
    """Manages WebSocket connections to an exchange for one symbol.

    Provides:
    - Real-time order status updates (fills, cancellations)
    - Real-time ticker (bid/ask) updates
    - Auto-reconnection on disconnect
    - Graceful fallback: if WS fails, caller uses REST polling
    """

    def __init__(
        self,
        exchange_id: str,
        api_key: str,
        api_secret: str,
        symbol: str,
        *,
        testnet: bool = True,
        on_order: OrderEventCallback | None = None,
        on_ticker: TickerCallback | None = None,
    ) -> None:
        self.exchange_id = exchange_id.lower()
        self.symbol = symbol
        self.testnet = testnet
        self._on_order = on_order
        self._on_ticker = on_ticker

        # Create ccxt.pro exchange instance for WebSocket
        exchange_class = getattr(ccxtpro, self.exchange_id)
        options: dict[str, Any] = {"defaultType": "spot"}
        if self.exchange_id == "binance":
            options["recvWindow"] = 5000

        config: dict[str, Any] = {
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "timeout": 30000,
            "options": options,
        }
        socks_proxy = get_settings().SOCKS_PROXY
        if socks_proxy:
            config["socksProxy"] = socks_proxy

        self._exchange = exchange_class(config)
        if testnet and hasattr(self._exchange, "set_sandbox_mode"):
            self._exchange.set_sandbox_mode(True)

        # State
        self._tasks: list[asyncio.Task] = []
        self._running = False
        self._connected = False
        self._last_ticker: Ticker | None = None
        self._last_ticker_ts: float = 0.0
        self._reconnect_delay: float = 1.0

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def last_ticker(self) -> Ticker | None:
        """Most recent ticker from WS stream (None if no data yet)."""
        return self._last_ticker

    @property
    def ticker_age_sec(self) -> float:
        """Seconds since last ticker update."""
        if self._last_ticker_ts == 0:
            return float("inf")
        return time.monotonic() - self._last_ticker_ts

    async def start(self) -> None:
        """Start WS listener tasks."""
        if self._running:
            return
        self._running = True
        self._tasks = [
            asyncio.create_task(self._watch_orders_loop(), name="ws_orders"),
            asyncio.create_task(self._watch_ticker_loop(), name="ws_ticker"),
        ]
        log.info(
            "ws_stream.started",
            exchange=self.exchange_id,
            symbol=self.symbol,
            testnet=self.testnet,
        )

    async def stop(self) -> None:
        """Stop WS listeners and close connection."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        self._connected = False
        try:
            await self._exchange.close()
        except Exception:
            pass
        log.info("ws_stream.stopped", exchange=self.exchange_id, symbol=self.symbol)

    # ------------------------------------------------------------------
    # Order stream
    # ------------------------------------------------------------------

    async def _watch_orders_loop(self) -> None:
        """Listen for order updates via WebSocket."""
        while self._running:
            try:
                orders = await self._exchange.watch_orders(self.symbol)
                self._connected = True
                self._reconnect_delay = 1.0

                for raw_order in orders:
                    event = self._parse_order(raw_order)
                    if event and self._on_order:
                        try:
                            await self._on_order(event)
                        except Exception as exc:
                            log.error("ws_stream.callback_error", error=str(exc)[:200])

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._connected = False
                log.warning(
                    "ws_stream.orders_disconnected",
                    exchange=self.exchange_id,
                    error=str(exc)[:200],
                    reconnect_in=self._reconnect_delay,
                )
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 30.0)

    def _parse_order(self, raw: dict) -> WsOrderEvent | None:
        """Parse ccxt order dict into WsOrderEvent."""
        try:
            status_str = str(raw.get("status", "")).lower()
            status_map = {
                "open": OrderStatus.PLACED,
                "closed": OrderStatus.FILLED,
                "canceled": OrderStatus.CANCELLED,
                "cancelled": OrderStatus.CANCELLED,
                "expired": OrderStatus.CANCELLED,
                "rejected": OrderStatus.CANCELLED,
            }
            status = status_map.get(status_str)
            if status is None:
                return None

            side_str = str(raw.get("side", "")).lower()
            side = OrderSide.BUY if side_str == "buy" else OrderSide.SELL

            return WsOrderEvent(
                exchange_order_id=str(raw.get("id", "")),
                status=status,
                side=side,
                price=Decimal(str(raw.get("price") or 0)),
                amount=Decimal(str(raw.get("amount") or 0)),
                filled=Decimal(str(raw.get("filled") or 0)),
                timestamp=raw.get("timestamp", time.time() * 1000) / 1000,
            )
        except (ValueError, TypeError, KeyError) as exc:
            log.warning("ws_stream.parse_error", error=str(exc)[:100], raw=str(raw)[:200])
            return None

    # ------------------------------------------------------------------
    # Ticker stream
    # ------------------------------------------------------------------

    async def _watch_ticker_loop(self) -> None:
        """Listen for ticker updates via WebSocket."""
        while self._running:
            try:
                ticker = await self._exchange.watch_ticker(self.symbol)
                self._connected = True
                self._reconnect_delay = 1.0

                bid = Decimal(str(ticker.get("bid") or ticker.get("last") or 0))
                ask = Decimal(str(ticker.get("ask") or ticker.get("last") or 0))

                if bid > 0 and ask > 0:
                    t = Ticker(bid=bid, ask=ask)
                    self._last_ticker = t
                    self._last_ticker_ts = time.monotonic()

                    if self._on_ticker:
                        try:
                            await self._on_ticker(t)
                        except Exception as exc:
                            log.error("ws_stream.ticker_callback_error", error=str(exc)[:200])

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._connected = False
                log.warning(
                    "ws_stream.ticker_disconnected",
                    exchange=self.exchange_id,
                    error=str(exc)[:200],
                    reconnect_in=self._reconnect_delay,
                )
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 30.0)
