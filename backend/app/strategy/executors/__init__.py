"""Фабрика и публичные экспорты исполнителей ордеров."""

from __future__ import annotations

from app.strategy.paper_executor import PaperExecutor

from ..base_executor import BaseExecutor
from .ccxt_executor import SUPPORTED_EXCHANGES, CcxtExecutor


def create_executor(
    exchange: str,
    api_key: str,
    api_secret: str,
    *,
    testnet: bool = True,
    paper_mode: bool = False,
    symbol: str = "BTC/USDT",
) -> BaseExecutor:
    if paper_mode:
        return PaperExecutor()

    exchange_lower = exchange.lower()
    if exchange_lower not in SUPPORTED_EXCHANGES:
        raise ValueError(
            f"Unsupported exchange: {exchange}. Supported: {list(SUPPORTED_EXCHANGES)}"
        )

    return CcxtExecutor(
        exchange_id=exchange_lower,
        api_key=api_key,
        api_secret=api_secret,
        testnet=testnet,
        symbol=symbol,
    )


__all__ = [
    "SUPPORTED_EXCHANGES",
    "BaseExecutor",
    "CcxtExecutor",
    "PaperExecutor",
    "create_executor",
]
