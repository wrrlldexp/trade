"""Сервис логирования бота — запись в БД + Redis pub/sub + console."""

from __future__ import annotations

import inspect
import json
import traceback as tb_module
import uuid
from datetime import UTC, datetime

from app.core.logging import get_logger
from app.core.redis_client import publish
from app.db import AsyncSessionLocal
from app.models.audit import BotLog
from app.models.enums import LogLevel

_structlog = get_logger("bot")

LOGS_CHANNEL = "bot:logs"


def _get_caller_source(stack_depth: int = 2) -> str:
    """Извлечь file:line:function из стека вызовов."""
    frame = inspect.currentframe()
    try:
        for _ in range(stack_depth):
            if frame is not None:
                frame = frame.f_back
        if frame is None:
            return "unknown"
        info = inspect.getframeinfo(frame)
        filename = info.filename
        idx = filename.find("app/")
        if idx != -1:
            filename = filename[idx:]
        else:
            idx = filename.find("worker/")
            if idx != -1:
                filename = filename[idx:]
        return f"{filename}:{info.lineno}:{info.function}"
    finally:
        del frame


async def _persist_log(
    level: LogLevel,
    message: str,
    source: str | None = None,
    grid_id: uuid.UUID | None = None,
    traceback_text: str | None = None,
    payload: dict | None = None,
) -> None:
    """Сохранить лог в БД в отдельной сессии."""
    try:
        async with AsyncSessionLocal() as session:
            entry = BotLog(
                level=level,
                message=message,
                source=source,
                grid_id=grid_id,
                traceback=traceback_text,
                payload=payload,
            )
            session.add(entry)
            await session.commit()
    except Exception:
        _structlog.warning("bot_logger.persist_failed", message=message)


async def _publish_log(
    level: LogLevel,
    message: str,
    source: str | None = None,
    grid_id: str | None = None,
    traceback_text: str | None = None,
) -> None:
    """Опубликовать лог в Redis для WebSocket с переводом через LogTranslator."""
    from app.core.log_translator import format_for_frontend, translate_bot_log

    translated = translate_bot_log(message, level=level.value, source=source, traceback_text=traceback_text)
    translation = format_for_frontend(translated)

    event = {
        "level": level.value,
        "message": message,
        "source": source,
        "grid_id": grid_id,
        "traceback": traceback_text[:500] if traceback_text else None,
        "timestamp": datetime.now(UTC).isoformat(),
        "translated": translation,
    }
    await publish(LOGS_CHANNEL, json.dumps(event, ensure_ascii=False))


async def log(
    level: LogLevel,
    message: str,
    *,
    grid_id: uuid.UUID | None = None,
    payload: dict | None = None,
    exc: Exception | None = None,
    stack_depth: int = 2,
) -> None:
    """Основная точка входа: консоль + БД + Redis."""
    source = _get_caller_source(stack_depth)
    traceback_text = None

    if exc is not None:
        traceback_text = "".join(tb_module.format_exception(type(exc), exc, exc.__traceback__))

    log_method = getattr(_structlog, level.value, _structlog.info)
    log_method(
        message,
        source=source,
        grid_id=str(grid_id) if grid_id else None,
        **(payload or {}),
    )

    await _persist_log(level, message, source, grid_id, traceback_text, payload)
    await _publish_log(level, message, source, str(grid_id) if grid_id else None, traceback_text)


async def info(message: str, **kwargs) -> None:
    await log(LogLevel.INFO, message, stack_depth=3, **kwargs)


async def warning(message: str, **kwargs) -> None:
    await log(LogLevel.WARNING, message, stack_depth=3, **kwargs)


async def error(message: str, **kwargs) -> None:
    await log(LogLevel.ERROR, message, stack_depth=3, **kwargs)


async def critical(message: str, **kwargs) -> None:
    await log(LogLevel.CRITICAL, message, stack_depth=3, **kwargs)
