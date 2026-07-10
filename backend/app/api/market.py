"""Market data API — OHLCV свечи и тикер (публичные данные биржи)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

import ccxt.async_support as ccxt

router = APIRouter(prefix="/api/market", tags=["market"])

# Кэш exchange-инстансов (без API-ключей — только публичные данные)
_exchanges: dict[str, ccxt.Exchange] = {}


async def _get_exchange(name: str) -> ccxt.Exchange:
    if name not in _exchanges:
        cls = getattr(ccxt, name, None)
        if cls is None:
            raise HTTPException(400, f"Биржа {name} не поддерживается")
        _exchanges[name] = cls({"enableRateLimit": True})
    return _exchanges[name]


@router.get("/ohlcv")
async def get_ohlcv(
    exchange: str = Query("bybit"),
    symbol: str = Query("BTC/USDT"),
    timeframe: str = Query("1m"),
    limit: int = Query(500, ge=10, le=1500),
):
    """Возвращает OHLCV-свечи с биржи."""
    ex = await _get_exchange(exchange)
    try:
        if not ex.markets:
            await ex.load_markets()
        ohlcv = await ex.fetch_ohlcv(symbol, timeframe, limit=limit)
    except Exception as e:
        raise HTTPException(502, f"Ошибка получения свечей: {e}") from e

    return [
        {
            "time": int(row[0] / 1000),  # Unix seconds для lightweight-charts
            "open": row[1],
            "high": row[2],
            "low": row[3],
            "close": row[4],
            "volume": row[5],
        }
        for row in ohlcv
    ]


@router.get("/ticker")
async def get_ticker(
    exchange: str = Query("bybit"),
    symbol: str = Query("BTC/USDT"),
):
    """Возвращает текущий тикер (bid/ask/last)."""
    ex = await _get_exchange(exchange)
    try:
        if not ex.markets:
            await ex.load_markets()
        ticker = await ex.fetch_ticker(symbol)
    except Exception as e:
        raise HTTPException(502, f"Ошибка получения тикера: {e}") from e

    return {
        "bid": ticker.get("bid"),
        "ask": ticker.get("ask"),
        "last": ticker.get("last"),
        "symbol": symbol,
    }
