"""Модели торговых сеток и их ордеров."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import GridMode, GridStatus, OrderSide, OrderStatus, StrategyType
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.exchange_account import ExchangeAccount


class Grid(Base, UUIDMixin, TimestampMixin):
    """Торговая сетка."""

    __tablename__ = "grids"

    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        ForeignKey("exchange_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)  # "BTC/USDT"

    mode: Mapped[GridMode] = mapped_column(
        Enum(GridMode, name="grid_mode", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        default=GridMode.PAPER,
    )
    status: Mapped[GridStatus] = mapped_column(
        Enum(GridStatus, name="grid_status", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        default=GridStatus.DRAFT,
    )
    strategy: Mapped[StrategyType] = mapped_column(
        Enum(StrategyType, name="strategy_type", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        default=StrategyType.SIMPLE,
    )

    # Параметры сетки
    lot_size: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    lot_quote: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 8), nullable=True, default=None
    )  # Лот в котировочной валюте (напр. 2.5 USDT) — пересчёт в base при каждом ордере
    profit_step: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    grid_step: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    levels_above: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    levels_below: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    # Адаптивность — rebuild (для простых стратегий)
    rebuild_timeout_sec: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3600
    )
    last_boundary_hit_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Адаптивная подсетка (strategy 5, 6) — из legacy
    adaptive_timer_sec: Mapped[int] = mapped_column(
        Integer, nullable=False, default=15
    )
    adaptive_top_order_idx: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    adaptive_bottom_order_idx: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    prepay_base: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False, default=0
    )  # prepayBtc — аванс в базовой валюте
    prepay_quote: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False, default=0
    )  # prepayCny — аванс в котировочной валюте
    prepay_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False, default=0
    )  # объём аванса на один ордер
    prepay_base_tail: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False, default=0
    )  # остаток аванса base
    prepay_quote_tail: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False, default=0
    )  # остаток аванса quote

    # Тик-интервал (секунды) — чем меньше, тем быстрее реакция
    tick_interval_sec: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False, default=1.0
    )

    # Статистика
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False, default=0
    )

    # Стартовый объём средств при создании сетки (USDT)
    start_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False, default=0
    )

    # Авто-конвертация прибыли (например "USDC")
    auto_convert_to: Mapped[str | None] = mapped_column(
        String(10), nullable=True, default=None
    )
    unconverted_pnl: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False, default=0
    )

    created_by_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stopped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Связи
    account: Mapped["ExchangeAccount"] = relationship(back_populates="grids")
    orders: Mapped[list["GridOrder"]] = relationship(
        back_populates="grid",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Grid {self.name} {self.symbol} {self.strategy.value} {self.status.value}>"


class GridOrder(Base, UUIDMixin, TimestampMixin):
    """Один ордер сетки."""

    __tablename__ = "grid_orders"

    grid_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        ForeignKey("grids.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Позиция в сетке (аналог id ордера в legacy для определения границ подсетки)
    grid_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    side: Mapped[OrderSide] = mapped_column(
        Enum(OrderSide, name="order_side", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        default=OrderStatus.PENDING,
        index=True,
    )

    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    price_sell: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False, default=0
    )  # priceSell из legacy — цена продажи для пары
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)

    exchange_order_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )

    # Legacy-поля для адаптивных стратегий
    prepay: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False, default=0
    )  # prepay — объём аванса на этот ордер
    re_buy: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )  # reBuy — нужна перекупка
    re_sell: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )  # reSell — нужна перепродажа
    profit: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False, default=0
    )  # накопленная прибыль по этому ордеру
    count_complete: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )  # кол-во завершённых циклов buy→sell

    filled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Связи
    grid: Mapped["Grid"] = relationship(back_populates="orders")

    def __repr__(self) -> str:
        return f"<GridOrder #{self.grid_index} {self.side.value} @ {self.price} [{self.status.value}]>"
