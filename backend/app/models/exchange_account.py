"""Модель биржевых аккаунтов (Binance keys)."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, LargeBinary, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.crypto import decrypt
from app.db import Base
from app.models.mixins import TimestampMixin, UUIDMixin
from app.strategy.executors import create_executor

if TYPE_CHECKING:
    from app.models.grid import Grid
    from app.models.user import User
    from app.strategy.base_executor import BaseExecutor


class ExchangeAccount(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "exchange_accounts"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    exchange: Mapped[str] = mapped_column(String(50), default="binance", nullable=False)

    # Зашифрованные ключи (Fernet)
    api_key_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    api_secret_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    is_testnet: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Связи
    owner: Mapped["User"] = relationship(back_populates="exchange_accounts")
    grids: Mapped[list["Grid"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ExchangeAccount {self.name} ({self.exchange})>"

    def decrypt_api_key(self) -> str:
        return decrypt(self.api_key_enc)

    def decrypt_api_secret(self) -> str:
        return decrypt(self.api_secret_enc)

    def to_executor(self, *, paper_mode: bool = False, symbol: str = "BTC/USDT") -> "BaseExecutor":
        return create_executor(
            exchange=self.exchange,
            api_key="" if paper_mode else self.decrypt_api_key(),
            api_secret="" if paper_mode else self.decrypt_api_secret(),
            testnet=self.is_testnet,
            paper_mode=paper_mode,
            symbol=symbol,
        )
