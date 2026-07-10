"""Тесты фабрики исполнителей."""

from app.strategy.executors import CcxtExecutor, PaperExecutor, create_executor


def test_create_executor_returns_paper_executor_in_paper_mode() -> None:
    executor = create_executor("binance", "key", "secret", paper_mode=True)

    assert isinstance(executor, PaperExecutor)


def test_create_executor_supports_bybit() -> None:
    executor = create_executor("bybit", "key", "secret", testnet=True, symbol="ETH/USDT")

    assert isinstance(executor, CcxtExecutor)
    assert executor.exchange_id == "bybit"
    assert executor.symbol == "ETH/USDT"


def test_create_executor_rejects_unknown_exchange() -> None:
    try:
        create_executor("kraken", "key", "secret")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for unsupported exchange")
