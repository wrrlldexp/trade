"""Совместимый live executor через ccxt."""

from __future__ import annotations

from app.strategy.executors.ccxt_executor import CcxtExecutor


class LiveExecutor(CcxtExecutor):
    """Обратная совместимость для существующих импортов."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        is_testnet: bool = False,
        symbol: str = "BTC/USDT",
        exchange_id: str = "binance",
    ) -> None:
        super().__init__(
            exchange_id=exchange_id,
            api_key=api_key,
            api_secret=api_secret,
            testnet=is_testnet,
            symbol=symbol,
        )
