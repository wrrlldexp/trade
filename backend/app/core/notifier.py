"""Единый модуль уведомлений.

Каналы доставки:
1. bot_logger (БД + Redis /ws/logs) — всегда
2. Redis канал "alerts" — для будущего Telegram-бота
3. Telegram (будет добавлен позже — просто добавить send_telegram())

Использование:
    from app.core.notifier import notify
    await notify("Контейнер backend упал!", level="critical", channel="monitoring")
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from app.core import bot_logger
from app.core.redis_client import publish
from app.models.enums import LogLevel

ALERTS_CHANNEL = "alerts"

# Уровни, которые отправляются в Telegram (когда подключим)
_TELEGRAM_LEVELS = {"error", "critical"}


async def notify(
    message: str,
    *,
    level: str = "info",
    channel: str = "system",
    grid_id: UUID | None = None,
    payload: dict | None = None,
) -> None:
    """Отправить уведомление во все каналы.

    Args:
        message: Текст уведомления (на русском).
        level: info | warning | error | critical
        channel: Категория — monitoring | trading | security | system
        grid_id: Привязка к сетке (опционально).
        payload: Дополнительные данные.
    """
    log_level = LogLevel(level) if level in LogLevel.__members__.values() else LogLevel.INFO

    # 1. Пишем в bot_logger (БД + консоль + /ws/logs)
    await bot_logger.log(
        log_level,
        message,
        grid_id=grid_id,
        payload={"channel": channel, **(payload or {})},
        stack_depth=3,
    )

    # 2. Публикуем в Redis канал alerts (для Telegram-бота)
    alert = {
        "level": level,
        "channel": channel,
        "message": message,
        "grid_id": str(grid_id) if grid_id else None,
        "payload": payload,
        "timestamp": datetime.now(UTC).isoformat(),
        "send_telegram": level in _TELEGRAM_LEVELS,
    }
    await publish(ALERTS_CHANNEL, json.dumps(alert, ensure_ascii=False))

    # 3. Telegram — TODO: когда подключим aiogram
    # if level in _TELEGRAM_LEVELS:
    #     await send_telegram(message, level=level, payload=payload)
