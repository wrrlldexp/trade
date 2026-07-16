"""Strategy worker — event-driven architecture with WebSocket + reconciliation fallback."""

import asyncio
import json
import signal
import time
import uuid
from collections.abc import Awaitable
from typing import cast

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app.core import bot_logger
from app.core import grid_activity_logger
from app.core.logging import configure_logging, get_logger
from app.core.redis_client import consume_local_channel, get_redis_client
from app.db import AsyncSessionLocal
from app.models import Grid, GridMode, GridStatus
from app.models.enums import OrderStatus
from app.services.grid_service import process_ws_fill, stop_grid, tick_grid, registry
from app.services.stats_collector import GridStatsCollector
from app.strategy.executors.ws_stream import ExchangeWsStream, WsOrderEvent

configure_logging()
log = get_logger("worker")

_shutdown = asyncio.Event()
_tasks: dict[uuid.UUID, asyncio.Task] = {}
_ws_streams: dict[uuid.UUID, ExchangeWsStream] = {}
_last_tick: dict[uuid.UUID, float] = {}

HEARTBEAT_KEY = "worker:heartbeat"
HEARTBEAT_INTERVAL = 10
CONTROL_CHANNEL = "worker:control"
TICK_TIMEOUT = 120  # max seconds per tick
WATCHDOG_INTERVAL = 60
WATCHDOG_STALE_THRESHOLD = 300

# Reconciliation interval: full tick every 30s as safety net (WS handles real-time)
RECONCILE_INTERVAL = 30.0
# Fast tick interval when WS is NOT connected (fallback to polling)
POLL_INTERVAL = 1.0


def _handle_signal(sig: int) -> None:
    log.info("worker.signal_received", signal=sig)
    _shutdown.set()


async def main() -> None:
    log.info("worker.starting")

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal, sig)

    log.info("worker.ready", note="Event-driven worker: WS real-time + reconciliation fallback")
    await bot_logger.info("Воркер запущен (event-driven: WebSocket + reconciliation)")

    async def run_grid_loop(grid_id: uuid.UUID) -> None:
        """Main grid loop: uses WS for instant fills, reconcile tick as fallback."""
        # Read tick interval from DB
        tick_interval = POLL_INTERVAL
        grid_row = None
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Grid).where(Grid.id == grid_id))
                grid_row = result.scalar_one_or_none()
                if grid_row and grid_row.tick_interval_sec:
                    tick_interval = float(grid_row.tick_interval_sec)
        except Exception:
            pass

        # Start WebSocket stream for this grid
        ws_stream = await _start_ws_stream(grid_id, grid_row)

        consecutive_timeouts = 0

        while not _shutdown.is_set():
            try:
                # Determine tick interval based on WS connection state
                if ws_stream and ws_stream.connected:
                    # WS is connected — reconcile less frequently
                    current_interval = RECONCILE_INTERVAL
                else:
                    # WS not available — poll at normal speed
                    current_interval = tick_interval

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
                if consecutive_timeouts >= 3:
                    await bot_logger.warning(
                        "3 таймаута подряд — пересоздаю подключение к бирже",
                        grid_id=grid_id,
                    )
                    await _restart_grid_runtime(grid_id)
                    ws_stream = await _start_ws_stream(grid_id, grid_row)
                    consecutive_timeouts = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if "No row was found" in str(exc):
                    await bot_logger.warning(
                        "Сетка удалена из БД — останавливаю цикл",
                        grid_id=grid_id,
                    )
                    await _cleanup_grid(grid_id)
                    return
                await bot_logger.error(
                    f"Ошибка в цикле сетки: {exc}",
                    grid_id=grid_id,
                    exc=exc,
                )
            await asyncio.sleep(current_interval)

    async def _start_ws_stream(grid_id: uuid.UUID, grid_row: Grid | None = None) -> ExchangeWsStream | None:
        """Start WebSocket stream for a grid. Returns stream or None if failed."""
        # Stop existing stream
        old_stream = _ws_streams.pop(grid_id, None)
        if old_stream:
            try:
                await old_stream.stop()
            except Exception:
                pass

        # Always reload with account relationship
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Grid).where(Grid.id == grid_id).options(
                        selectinload(Grid.account)
                    )
                )
                grid_row = result.scalar_one_or_none()
        except Exception:
            return None

        if grid_row is None or grid_row.account is None:
            return None

        # No WS for paper mode grids
        if grid_row.mode == GridMode.PAPER:
            return None

        account = grid_row.account

        # Create order event callback
        async def on_order_event(event: WsOrderEvent) -> None:
            """Handle real-time order event from exchange WebSocket."""
            if event.status == OrderStatus.FILLED:
                log.info(
                    "ws_stream.fill_detected",
                    grid_id=str(grid_id),
                    order_id=event.exchange_order_id,
                    side=event.side.value,
                    price=str(event.price),
                )
                try:
                    async with AsyncSessionLocal() as session:
                        processed = await process_ws_fill(
                            session, grid_id, event.exchange_order_id
                        )
                        if processed:
                            await session.commit()
                            log.info(
                                "ws_stream.fill_processed",
                                grid_id=str(grid_id),
                                order_id=event.exchange_order_id,
                            )
                except Exception as exc:
                    log.error(
                        "ws_stream.fill_processing_error",
                        grid_id=str(grid_id),
                        order_id=event.exchange_order_id,
                        error=str(exc)[:200],
                    )
            elif event.status == OrderStatus.CANCELLED:
                log.info(
                    "ws_stream.cancel_detected",
                    grid_id=str(grid_id),
                    order_id=event.exchange_order_id,
                )

        try:
            stream = ExchangeWsStream(
                exchange_id=account.exchange,
                api_key=account.decrypt_api_key(),
                api_secret=account.decrypt_api_secret(),
                symbol=grid_row.symbol,
                testnet=account.is_testnet,
                on_order=on_order_event,
            )
            await stream.start()
            _ws_streams[grid_id] = stream

            # Link WS stream to executor for ticker feed
            executor = registry.executors.get(grid_id)
            if executor and hasattr(executor, "_ws_stream"):
                executor._ws_stream = stream

            await bot_logger.info(
                f"WebSocket подключён: {account.exchange} {grid_row.symbol}",
                grid_id=grid_id,
            )
            return stream
        except Exception as exc:
            log.warning(
                "ws_stream.start_failed",
                grid_id=str(grid_id),
                error=str(exc)[:200],
            )
            await bot_logger.warning(
                f"WebSocket не удалось подключить (fallback на polling): {exc}",
                grid_id=grid_id,
            )
            return None

    async def _restart_grid_runtime(grid_id: uuid.UUID) -> None:
        """Reset executor/engine/state for a grid."""
        executor = registry.executors.pop(grid_id, None)
        if executor:
            try:
                await asyncio.wait_for(executor.close(), timeout=5)
            except Exception:
                pass
        registry.engines.pop(grid_id, None)
        registry.states.pop(grid_id, None)

    async def _cleanup_grid(grid_id: uuid.UUID) -> None:
        """Full cleanup when grid is removed."""
        _tasks.pop(grid_id, None)
        _last_tick.pop(grid_id, None)
        # Stop WS
        stream = _ws_streams.pop(grid_id, None)
        if stream:
            try:
                await stream.stop()
            except Exception:
                pass
        # Clear runtime
        registry.executors.pop(grid_id, None)
        registry.engines.pop(grid_id, None)
        registry.states.pop(grid_id, None)

    async def publish_heartbeat() -> None:
        """Publish heartbeat to Redis every N seconds."""
        while not _shutdown.is_set():
            try:
                r = get_redis_client()
                ws_connected = {
                    str(gid): stream.connected
                    for gid, stream in _ws_streams.items()
                }
                data = json.dumps({
                    "ts": time.time(),
                    "active_grids": len(_tasks),
                    "grid_ids": [str(gid) for gid in _tasks],
                    "ws_connected": ws_connected,
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
        action = command.get("action", "")
        if action == "stop_all":
            await bot_logger.warning("Команда: остановить все сетки")
            for grid_id in list(_tasks.keys()):
                _tasks[grid_id].cancel()
                _tasks.pop(grid_id, None)
                # Stop WS stream
                stream = _ws_streams.pop(grid_id, None)
                if stream:
                    try:
                        await stream.stop()
                    except Exception:
                        pass
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
            # Stop WS stream
            stream = _ws_streams.pop(grid_id, None)
            if stream:
                try:
                    await stream.stop()
                except Exception:
                    pass
            async with AsyncSessionLocal() as session:
                await stop_grid(session, grid_id)
                await session.commit()

    # Bootstrap: start loops for all RUNNING grids
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Grid).where(Grid.status == GridStatus.RUNNING))
            for grid in result.scalars().all():
                _tasks[grid.id] = asyncio.create_task(run_grid_loop(grid.id))
    except SQLAlchemyError:
        log.warning(
            "worker.bootstrap_pending_migrations",
            note="Could not load active grids during bootstrap.",
        )

    async def sync_running_grids() -> None:
        """Periodically check DB for running grids not being ticked."""
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
                    await bot_logger.warning("Синхронизация: запускаю пропущенную сетку", grid_id=grid_id)
                    _tasks[grid_id] = asyncio.create_task(run_grid_loop(grid_id))
            except Exception:
                pass

    async def watchdog() -> None:
        """Restart stuck grid loops."""
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
                    task.cancel()
                    try:
                        await asyncio.wait_for(asyncio.shield(task), timeout=5)
                    except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                        pass
                    # Stop WS and recreate
                    stream = _ws_streams.pop(grid_id, None)
                    if stream:
                        try:
                            await stream.stop()
                        except Exception:
                            pass
                    await _restart_grid_runtime(grid_id)
                    _last_tick[grid_id] = now
                    _tasks[grid_id] = asyncio.create_task(run_grid_loop(grid_id))

    async def periodic_api_stats() -> None:
        """Log API stats every 5 minutes for all active grids."""
        while not _shutdown.is_set():
            await asyncio.sleep(300)
            for grid_id in list(_tasks.keys()):
                try:
                    await grid_activity_logger.log_api_stats(grid_id)
                except Exception:
                    pass

    async def ws_health_monitor() -> None:
        """Monitor WS connections, reconnect if needed, link to executors."""
        while not _shutdown.is_set():
            await asyncio.sleep(15)
            for grid_id in list(_tasks.keys()):
                stream = _ws_streams.get(grid_id)
                # Ensure executor has WS stream reference
                executor = registry.executors.get(grid_id)
                if executor and hasattr(executor, "_ws_stream"):
                    if stream and stream.connected:
                        executor._ws_stream = stream
                    else:
                        executor._ws_stream = None

                # If stream is dead, try to restart
                if stream and not stream.connected:
                    log.warning("ws_health.disconnected", grid_id=str(grid_id))

    # Stats collector — 60-second snapshots of grid/account metrics
    stats_collector = GridStatsCollector(AsyncSessionLocal)
    stats_collector_task = asyncio.create_task(stats_collector.run_forever())

    command_task = asyncio.create_task(consume_commands())
    heartbeat_task = asyncio.create_task(publish_heartbeat())
    sync_task = asyncio.create_task(sync_running_grids())
    watchdog_task = asyncio.create_task(watchdog())
    api_stats_task = asyncio.create_task(periodic_api_stats())
    ws_health_task = asyncio.create_task(ws_health_monitor())

    while not _shutdown.is_set():
        try:
            await asyncio.wait_for(_shutdown.wait(), timeout=30.0)
        except TimeoutError:
            ws_status = {str(gid): s.connected for gid, s in _ws_streams.items()}
            log.info("worker.heartbeat", active_grids=len(_tasks), ws_status=ws_status)

    # Graceful shutdown
    all_tasks_to_cancel = [
        command_task, heartbeat_task, sync_task, watchdog_task,
        api_stats_task, ws_health_task, stats_collector_task, *_tasks.values(),
    ]
    for task in all_tasks_to_cancel:
        task.cancel()
    await asyncio.gather(*all_tasks_to_cancel, return_exceptions=True)

    # Stop all WS streams
    for stream in _ws_streams.values():
        try:
            await stream.stop()
        except Exception:
            pass
    _ws_streams.clear()

    # Close all exchange connections
    for grid_id, executor in list(registry.executors.items()):
        try:
            await asyncio.wait_for(executor.close(), timeout=5)
        except Exception:
            pass
    registry.executors.clear()
    registry.engines.clear()
    registry.states.clear()
    registry.reconcilers.clear()

    await bot_logger.info("Воркер остановлен")
    log.info("worker.stopped")


if __name__ == "__main__":
    asyncio.run(main())
