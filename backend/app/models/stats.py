"""Модели снимков статистики — аналог legacy `statistics` и `apiStatistics`."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class GridStatSnapshot(Base):
    """Снимок состояния сетки. Аналог legacy `statistics`."""

    __tablename__ = "grid_stat_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    grid_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        ForeignKey("grids.id", ondelete="CASCADE"),
        nullable=False,
    )

    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    course: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)

    profit_math: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    net_asset: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    net_asset_sag: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    profit_drift: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)

    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    placed_orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_grid_stat_snapshots_grid_id_time", "grid_id", "time"),
        Index("ix_grid_stat_snapshots_time", "time"),
    )

    def __repr__(self) -> str:
        return f"<GridStatSnapshot grid={self.grid_id} t={self.time}>"


class AccountStatSnapshot(Base):
    """Снимок баланса аккаунта. Аналог legacy `apiStatistics`."""

    __tablename__ = "account_stat_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        ForeignKey("exchange_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    net_asset: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    base_balance: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    quote_balance: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)

    __table_args__ = (
        Index("ix_account_stat_snapshots_account_id_time", "account_id", "time"),
        Index("ix_account_stat_snapshots_time", "time"),
    )

    def __repr__(self) -> str:
        return f"<AccountStatSnapshot account={self.account_id} t={self.time}>"
