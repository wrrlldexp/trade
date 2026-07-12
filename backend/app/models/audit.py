"""Модели событий торговли и аудита."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, Numeric, String, Uuid, func
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import LogLevel, TradeEventType


class TradeEvent(Base):
    """Журнал торговых событий (для аналитики и графиков)."""

    __tablename__ = "trade_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    grid_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        ForeignKey("grids.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(),
        ForeignKey("grid_orders.id", ondelete="SET NULL"),
        nullable=True,
    )

    event_type: Mapped[TradeEventType] = mapped_column(
        Enum(TradeEventType, name="trade_event_type", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )

    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    pnl_delta: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)

    payload: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<TradeEvent {self.event_type.value} grid={self.grid_id}>"


class AuditLog(Base):
    """Журнал действий пользователей в панели."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(45).with_variant(INET, "postgresql"), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    payload: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} user={self.user_id}>"


class BotLog(Base):
    """Журнал работы бота (логи, ошибки, события)."""

    __tablename__ = "bot_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    level: Mapped[LogLevel] = mapped_column(
        Enum(LogLevel, name="log_level", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        index=True,
    )

    message: Mapped[str] = mapped_column(String(1000), nullable=False)

    source: Mapped[str | None] = mapped_column(String(500), nullable=True)

    grid_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(),
        ForeignKey("grids.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    traceback: Mapped[str | None] = mapped_column(String(10000), nullable=True)

    payload: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<BotLog {self.level.value} {self.message[:50]}>"


class GridActivityLog(Base):
    """Детальный лог активности сетки — тики, fill-ы, перестроения, API-статистика."""

    __tablename__ = "grid_activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    grid_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        ForeignKey("grids.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    event: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    data: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<GridActivityLog {self.event} grid={self.grid_id}>"


class GridAnalyticsSession(Base):
    """Сессия аналитики: 24-часовой снэпшот после изменения настроек сетки пользователем."""

    __tablename__ = "grid_analytics_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    grid_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        ForeignKey("grids.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # Снэпшот настроек до и после
    settings_before: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False,
    )
    settings_after: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False,
    )

    def __repr__(self) -> str:
        return f"<GridAnalyticsSession grid={self.grid_id} {self.started_at}>"
