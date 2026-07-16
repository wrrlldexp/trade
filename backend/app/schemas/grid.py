"""Схемы сеток."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import GridMode, StrategyType
from app.schemas.common import GridOrderResponse, GridResponse, TradeEventResponse


class GridCreate(BaseModel):
    account_id: UUID  # M-7: UUID вместо str — автоматическая валидация 422
    name: str = Field(min_length=1, max_length=100)
    symbol: str = "BTC/USDT"
    mode: GridMode = GridMode.PAPER
    strategy: StrategyType = StrategyType.SIMPLE
    lot_size: Decimal | None = Field(default=None, gt=0, description="Размер лота в базовой валюте")
    lot_quote: Decimal | None = Field(default=None, gt=0, description="Размер лота в котировочной валюте (USDT) — пересчёт при каждом ордере")

    @model_validator(mode="after")
    def check_lot(self) -> "GridCreate":
        if not self.lot_size and not self.lot_quote:
            raise ValueError("Укажите lot_size или lot_quote")
        # Если задан lot_quote но не lot_size — ставим заглушку, реальный расчёт по lot_quote в engine
        if self.lot_quote and not self.lot_size:
            self.lot_size = Decimal("0.00000001")
        return self
    profit_step: Decimal = Field(gt=0, description="Шаг профита")
    grid_step: Decimal = Field(gt=0, description="Шаг сетки")
    levels_above: int = Field(ge=0, le=100, description="Уровней выше центра")
    levels_below: int = Field(ge=0, le=100, description="Уровней ниже центра")
    rebuild_timeout_sec: int = Field(default=0, ge=0, le=86400)
    auto_convert_to: str | None = Field(default=None, max_length=10, description="Валюта для авто-конвертации прибыли (например USDC)")


class GridUpdate(BaseModel):
    name: str | None = None
    symbol: str | None = None
    strategy: StrategyType | None = None
    lot_size: Decimal | None = None
    lot_quote: Decimal | None = None
    profit_step: Decimal | None = None
    grid_step: Decimal | None = None
    levels_above: int | None = None
    levels_below: int | None = None
    rebuild_timeout_sec: int | None = None
    auto_convert_to: str | None = None


class GridDetailResponse(GridResponse):
    orders: list[GridOrderResponse]


class GridCollectionResponse(BaseModel):
    items: list[GridResponse]


class GridEventsResponse(BaseModel):
    items: list[TradeEventResponse]


class GridOrdersResponse(BaseModel):
    items: list[GridOrderResponse]
