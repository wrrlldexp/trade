"""Схемы аудита, логов и торговых событий."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import LogLevel


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: UUID | None
    action: str
    entity_type: str | None
    entity_id: str | None
    ip_address: str | None
    user_agent: str | None
    payload: dict | None
    created_at: datetime


class BotLogTranslation(BaseModel):
    """Переведённое сообщение лога."""

    severity: str
    title: str
    body: str | None = None
    emoji: str
    cause: str | None = None
    fix: str | None = None
    doc_ref: str | None = None


class BotLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    level: LogLevel
    message: str
    source: str | None
    grid_id: UUID | None
    traceback: str | None
    payload: dict | None
    created_at: datetime
    translated: BotLogTranslation | None = None


class BotLogListResponse(BaseModel):
    items: list[BotLogResponse]
    total: int


class TradeEventEnrichedResponse(BaseModel):
    """TradeEvent + имя сетки и пара для страницы сделок."""

    id: int
    grid_id: UUID
    grid_name: str
    symbol: str
    event_type: str
    price: str | None
    amount: str | None
    pnl_delta: str | None
    payload: dict | None
    created_at: datetime
