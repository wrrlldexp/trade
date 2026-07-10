"""Strategy worker — entrypoint."""

import asyncio
import json
import signal
import time
import uuid
from collections.abc import Awaitable
from typing import cast

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core import bot_logger
from app.core.logging import configure_logging, get_logger
from app.core.redis_client import consume_local_channel, get_redis_client
from app.db import AsyncSessionLocal
from app.models import Grid, GridStatus
from app.services.grid_service import stop_grid, tick_grid, registry

configure_logging()
log = get_logger("worker")

_shutdown = asyncio.Event()
_tasks: dict[uuid.UUID, asyncio.Task] = {}
_last_tick: dict[uuid.UUID, float] = {}

HEARTBEAT_KEY = "worker:heartbeat"
HEARTBEAT_INTERVAL = 10
CONTROL_CHANNEL = "worker:control"
TICK_TIMEOUT = 120  # max seconds per tick (rebuild can take 60s+ with throttle)
WATCHDOG_INTERVAL = 60  # check every 60s
WATCHDOG_STALE_THRESHOLD = 300  # if no tick for 5 minutes, restart loop


def _handle_signal(sig: int) -> None:
    log.info("worker.signal_received", signal=sig)
    _shutdown.set()


async def main() -> None:
    log.info("worker.starting")

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal, sig)

    log.info("worker.ready", note="Воркер слушает команды сеток и тикает активные grid-задачи.")
    await bot_logger.info("Воркер запущен, слушаю команды сеток")

    async def run_grid_loop(grid_id: uuid.UUID) -> None:
        tick_interval = 0.1
        consecutive_timeouts = 0

        while not _shutdown.is_set():
            try:
                async with AsyncSessionLocal() as session:
                    await asyncio.wait_for(
                        tick_grid(session, grid_id),
                        timeout=TICK_TIMEOUT,
                    )
                    await session.commit()
                _last_tick[grid_id] = time.monotonic()
                consecutive_timeouts = 0
            except asyncio.TimeoutError:
                consecutive_timeouts += 1
                await bot_logger.error(
                    f"Тик завис (таймаут {TICK_TIMEOUT}с, подряд: {consecutive_timeouts})",
                    grid_id=grid_id,
                )
                # After 3 consecutive timeouts, recreate the executor (fresh connection)
                if consecutive_timeouts >= 3:
                    await bot_logger.warning(
                        f"3 таймаута подряд — пересоздаю подключение к бирже",
                        grid_id=grid_id,
                    )
                    executor = registry.executors.pop(grid_id, None)
                    if executor:
                        try:
                            await asyncio.wait_for(executor.close(), timeout=5)
                        except Exception:
                            pass
                    registry.engines.pop(grid_id, None)
                    registry.states.pop(grid_id, None)
                    consecutive_timeouts = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # If grid was deleted from DB, stop the loop
                if "No row was found" in str(exc):
                    await bot_logger.warning(
                        f"Сетка удалена из БД — останавливаю цикл",
                        grid_id=grid_id,
                    )
                    _tasks.pop(grid_id, None)
                    _last_tick.pop(grid_id, None)
                    registry.executors.pop(grid_id, None)
                    registry.engines.pop(grid_id, None)
                    registry.states.pop(grid_id, None)
                    return
                await bot_logger.error(
                    f"Ошибка в цикле сетки: {exc}",
                    grid_id=grid_id,
                    exc=exc,
                )
            await asyncio.sleep(tick_interval)

    async def publish_heartbeat() -> None:
        """Публиковать heartbeat в Redis каждые N секунд."""
        while not _shutdown.is_set():
            try:
                r = get_redis_client()
                data = json.dumps({
                    "ts": time.time(),
                    "active_grids": len(_tasks),
                    "grid_ids": [str(gid) for gid in _tasks],
                })
                await cast(Awaitable[bool | None], r.set(HEARTBEAT_KEY, data, ex=HEARTBEAT_INTERVAL * 3))
            except Exception:
                pass
            await asyncio.sleep(HEARTBEAT_INTERVAL)

    async def consume_commands() -> None:
        pubsub = None
        try:
            try:
                redis = get_redis_client()
                pubsub = redis.pubsub()
                await pubsub.subscribe("grids:commands", CONTROL_CHANNEL)
            except Exception:
                pubsub = None

            while not _shutdown.is_set():
                if pubsub is not None:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    raw = message["data"] if message and message.get("data") else None
                    if raw:
                        parsed = json.loads(raw)
                        channel = message.get("channel", "")
                        if channel == CONTROL_CHANNEL:
                            await handle_control(parsed)
                        else:
                            await handle_command(parsed)
                else:
                    for raw in consume_local_channel("grids:commands"):
                        await handle_command(json.loads(raw))
                    for raw in consume_local_channel(CONTROL_CHANNEL):
                        await handle_control(json.loads(raw))
                await asyncio.sleep(0.2)
        finally:
            if pubsub is not None:
                await pubsub.unsubscribe("grids:commands", CONTROL_CHANNEL)
                await pubsub.aclose()

    async def handle_control(command: dict) -> None:
        """Обработка команд управления воркером."""
        action = command.get("action", "")
        if action == "stop_all":
            await bot_logger.warning("Команда: остановить все сетки")
            for grid_id in list(_tasks.keys()):
                _tasks[grid_id].cancel()
                _tasks.pop(grid_id, None)
                try:
                    async with AsyncSessionLocal() as session:
                        await stop_grid(session, grid_id)
                        await session.commit()
                except Exception as exc:
                    await bot_logger.error(f"Ошибка при остановке сетки: {exc}", grid_id=grid_id, exc=exc)
        elif action == "restart":
            await bot_logger.warning("Команда: перезагрузка воркера")
            _shutdown.set()

    async def handle_command(command: dict) -> None:
        # M-9: защита от битых сообщений
        try:
            grid_id = uuid.UUID(str(command["grid_id"]))
            action = command["action"]
        except (KeyError, ValueError) as exc:
            await bot_logger.warning(f"Некорректная команда: {exc}", payload={"raw": str(command)[:200]})
            return
        await bot_logger.info(f"Команда получена: {action}", grid_id=grid_id)
        if action == "start" and grid_id not in _tasks:
            _tasks[grid_id] = asyncio.create_task(run_grid_loop(grid_id))
        elif action == "stop" and grid_id in _tasks:
            _tasks[grid_id].cancel()
            _tasks.pop(grid_id, None)
            _last_tick.pop(grid_id, None)
            async with AsyncSessionLocal() as session:
                await stop_grid(session, grid_id)
                await session.commit()

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Grid).where(Grid.status == GridStatus.RUNNING))
            for grid in result.scalars().all():
                _tasks[grid.id] = asyncio.create_task(run_grid_loop(grid.id))
    except SQLAlchemyError:
        log.warning(
            "worker.bootstrap_pending_migrations",
            note="Could not load active grids during bootstrap. Ensure Alembic migrations are applied.",
        )

    async def sync_running_grids() -> None:
        """Периодически проверяем БД на running сетки, которые не тикаются."""
        while not _shutdown.is_set():
            await asyncio.sleep(30)
            try:
                async with AsyncSessionLocal() as session:
                    result = await session.execute(select(Grid).where(Grid.status == GridStatus.RUNNING))
                    db_running = {grid.id for grid in result.scalars().all()}
                active_ids = set(_tasks.keys())
                missing = db_running - active_ids
                for grid_id in missing:
                    log.warning("worker.sync_missing_grid", grid_id=str(grid_id))
                    await bot_logger.warning(f"Синхронизация: запускаю пропущенную сетку", grid_id=grid_id)
                    _tasks[grid_id] = asyncio.create_task(run_grid_loop(grid_id))
            except Exception:
                pass

    async def watchdog() -> None:
        """Перезапуск зависших grid-лупов."""
        while not _shutdown.is_set():
            await asyncio.sleep(WATCHDOG_INTERVAL)
            now = time.monotonic()
            for grid_id in list(_tasks.keys()):
                task = _tasks[grid_id]
                last = _last_tick.get(grid_id, now)
                stale = now - last
                if task.done():
                    log.warning("watchdog.task_dead", grid_id=str(grid_id))
                    await bot_logger.warning("Watchdog: тик-луп умер, перезапуск", grid_id=grid_id)
                    _tasks[grid_id] = asyncio.create_task(run_grid_loop(grid_id))
                elif stale > WATCHDOG_STALE_THRESHOLD:
                    log.warning("watchdog.stale_loop", grid_id=str(grid_id), stale_seconds=round(stale))
                    await bot_logger.warning(
                        f"Watchdog: тик не обновлялся {round(stale)}с — перезапуск",
                        grid_id=grid_id,
                    )
                    # Kill the stuck task and restart
                    task.cancel()
                    try:
                        await asyncio.wait_for(asyncio.shield(task), timeout=5)
                    except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                        pass
                    # Force-close executor to drop stuck connections
                    executor = registry.executors.pop(grid_id, None)
                    if executor:
                        try:
                            await asyncio.wait_for(executor.close(), timeout=5)
                        except Exception:
                            pass
                    registry.engines.pop(grid_id, None)
                    registry.states.pop(grid_id, None)
                    _last_tick[grid_id] = now
                    _tasks[grid_id] = asyncio.create_task(run_grid_loop(grid_id))

    command_task = asyncio.create_task(consume_commands())
    heartbeat_task = asyncio.create_task(publish_heartbeat())
    sync_task = asyncio.create_task(sync_running_grids())
    watchdog_task = asyncio.create_task(watchdog())

    while not _shutdown.is_set():
        try:
            await asyncio.wait_for(_shutdown.wait(), timeout=30.0)
        except TimeoutError:
            log.info("worker.heartbeat", active_grids=len(_tasks))

    # H-7: корректная остановка — отменяем и ждём завершения
    all_tasks_to_cancel = [command_task, heartbeat_task, sync_task, watchdog_task, *_tasks.values()]
    for task in all_tasks_to_cancel:
        task.cancel()
    await asyncio.gather(*all_tasks_to_cancel, return_exceptions=True)
    # Close all exchange connections
    for grid_id, executor in list(registry.executors.items()):
        try:
            await asyncio.wait_for(executor.close(), timeout=5)
        except Exception:
            pass
    registry.executors.clear()
    registry.engines.clear()
    registry.states.clear()

    await bot_logger.info("Воркер остановлен")
    log.info("worker.stopped")


if __name__ == "__main__":
    asyncio.run(main())
