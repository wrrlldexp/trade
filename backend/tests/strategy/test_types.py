from decimal import Decimal

from app.strategy.types import Ticker


def test_ticker_mid_uses_decimal() -> None:
    ticker = Ticker(bid=Decimal("99"), ask=Decimal("101"))
    assert ticker.mid == Decimal("100")
