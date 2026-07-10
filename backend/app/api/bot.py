"""API управления ботом (воркером) и мониторинг."""

from __future__ import annotations

import json
import time
from collections.abc import Awaitable
from typing import cast

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import bot_logger
from app.core.audit import log_action
from app.core.deps import require_role
from app.core.redis_client import get_redis_client, publish
from app.db import get_db
from app.models import User, UserRole
from app.services.grid_service import emergency_stop_all
from app.services.monitor import run_health_checks

router = APIRouter()

HEARTBEAT_KEY = "worker:heartbeat"
CONTROL_CHANNEL = "worker:control"


@router.get("/status")
async def bot_status(
    current_user: User = Depends(require_role(UserRole.VIEWER, UserRole.ADMIN, UserRole.SUPERADMIN)),
) -> dict:
    """Статус воркера: онлайн/оффлайн, активные сетки."""
    try:
        r = get_redis_client()
        raw = await cast(Awaitable[str | None], r.get(HEARTBEAT_KEY))
        if raw is None:
            return {"online": False, "active_grids": 0, "grid_ids": [], "last_seen": None}

        data = json.loads(raw)
        age = time.time() - data.get("ts", 0)
        return {
            "online": age < 35,
            "active_grids": data.get("active_grids", 0),
            "grid_ids": data.get("grid_ids", []),
            "last_seen": data.get("ts"),
            "age_sec": round(age, 1),
        }
    except Exception:
        return {"online": False, "active_grids": 0, "grid_ids": [], "last_seen": None}


@router.post("/emergency-stop")
async def bot_emergency_stop(
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Аварийная остановка: отменить ВСЕ ордеры на бирже и остановить все сетки."""
    # 1. Команда воркеру — немедленно прекратить тики
    await publish(CONTROL_CHANNEL, json.dumps({"action": "stop_all"}))
    # 2. Прямая отмена ордеров через grid_service (двойная страховка)
    result = await emergency_stop_all(db)
    await log_action(db, current_user.id, "bot.emergency_stop", request=request)
    await bot_logger.critical(
        f"АВАРИЙНАЯ ОСТАНОВКА инициирована пользователем {current_user.email}",
        payload={"user": current_user.email, **result},
    )
    return {
        "detail": "Аварийная остановка выполнена",
        **result,
    }


@router.post("/stop-all")
async def bot_stop_all(
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
) -> dict:
    """Остановить все активные сетки."""
    await publish(CONTROL_CHANNEL, json.dumps({"action": "stop_all"}))
    await bot_logger.warning(
        f"Все сетки остановлены пользователем {current_user.email}",
        payload={"user": current_user.email},
    )
    return {"detail": "Команда остановки отправлена"}


@router.post("/restart")
async def bot_restart(
    current_user: User = Depends(require_role(UserRole.SUPERADMIN)),
) -> dict:
    """Перезагрузить воркер. Docker автоматически поднимет новый экземпляр."""
    await publish(CONTROL_CHANNEL, json.dumps({"action": "restart"}))
    await bot_logger.warning(
        f"Воркер перезагружен пользователем {current_user.email}",
        payload={"user": current_user.email},
    )
    return {"detail": "Команда перезагрузки отправлена"}


@router.get("/health-check")
async def health_check(
    current_user: User = Depends(require_role(UserRole.VIEWER, UserRole.ADMIN, UserRole.SUPERADMIN)),
) -> dict:
    """Полная проверка здоровья системы: диск, RAM, CPU."""
    report = await run_health_checks()
    return report.to_dict()


@router.post("/health-check")
async def trigger_health_check() -> dict:
    """Запуск проверки из cron (без авторизации, только с localhost)."""
    report = await run_health_checks()
    return report.to_dict()
