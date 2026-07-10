from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.models.enums import StrategyType
from app.strategy.engine import GridEngine
from app.strategy.paper_executor import PaperExecutor
from app.strategy.types import GridParams


@pytest.fixture()
def default_params() -> GridParams:
    return GridParams(
        strategy=StrategyType.SIMPLE,
        lot_size=Decimal("0.1"),
        profit_step=Decimal("50"),
        grid_step=Decimal("100"),
        levels_above=3,
        levels_below=3,
        rebuild_timeout_sec=60,
    )


@pytest.fixture()
def paper_executor() -> PaperExecutor:
    return PaperExecutor(initial_base=Decimal("1"), initial_quote=Decimal("10000"), bid=Decimal("1000"), ask=Decimal("1000"))


@pytest.fixture()
def engine(default_params: GridParams, paper_executor: PaperExecutor) -> GridEngine:
    return GridEngine(default_params, paper_executor)


@pytest.fixture()
def now() -> datetime:
    return datetime.now(UTC)
