"""Схемы биржевых аккаунтов."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

ExchangeType = Literal["binance", "bybit"]


class ExchangeAccountCreate(BaseModel):
    name: str
    exchange: ExchangeType = "binance"
    api_key: str
    api_secret: str
    is_testnet: bool = False


class ExchangeAccountUpdate(BaseModel):
    name: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    is_testnet: bool | None = None
    is_active: bool | None = None


class ExchangeAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    exchange: ExchangeType
    is_testnet: bool
    is_active: bool
    created_at: datetime


class ExchangeAccountTestResponse(BaseModel):
    success: bool
    message: str | None = None
    balance: dict[str, str] | None = None
    exchange: ExchangeType | None = None
    testnet: bool | None = None
    error: str | None = None
