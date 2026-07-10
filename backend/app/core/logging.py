"""Конфигурация structlog для всего приложения."""

import logging
import sys

import structlog

from app.config import get_settings


def configure_logging() -> None:
    """Настройка structlog. Вызывать один раз при старте."""
    settings = get_settings()

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.is_development:
        # В dev — цветной вывод для людей
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        # В проде — JSON для систем сбора логов
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Получить логгер с именем."""
    return structlog.get_logger(name)
