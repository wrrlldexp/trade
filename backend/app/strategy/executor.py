"""Интерфейс исполнения ордеров."""

from __future__ import annotations

from app.strategy.base_executor import BaseExecutor


class Executor(BaseExecutor):
    """Совместимый alias для нового базового интерфейса исполнителей."""

    pass
