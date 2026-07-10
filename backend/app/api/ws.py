"""WebSocket API."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.bot_logger import LOGS_CHANNEL
from app.core.redis_client import consume_local_channel, get_redis_client, is_blacklisted
from app.core.security import decode_token

router = APIRouter()


async def _authenticate_ws(websocket: WebSocket, token: str | None) -> bool:
    """Проверяем JWT-токен для WebSocket-подключения."""
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return False
    try:
        payload = decode_token(token)
        if payload.typ != "access":
            await websocket.close(code=4001, reason="Invalid token type")
            return False
        if payload.jti and await is_blacklisted(payload.jti):
            await websocket.close(code=4001, reason="Token revoked")
            return False
    except ValueError:
        await websocket.close(code=4001, reason="Invalid token")
        return False
    return True


@router.websocket("/grids/{grid_id}")
async def grid_updates(websocket: WebSocket, grid_id: str, token: str | None = Query(default=None)) -> None:
    if not await _authenticate_ws(websocket, token):
        return

    await websocket.accept()
    channel = f"grid:{grid_id}:events"
    pubsub = None
    try:
        try:
            redis = get_redis_client()
            pubsub = redis.pubsub()
            await pubsub.subscribe(channel)
        except Exception:
            pubsub = None

        while True:
            if pubsub is not None:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message.get("data"):
                    await websocket.send_text(message["data"])
            else:
                for local_message in consume_local_channel(channel):
                    await websocket.send_text(local_message)
            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        pass
    finally:
        if pubsub is not None:
            await pubsub.unsubscribe(channel)
            await pubsub.close()


@router.websocket("/logs")
async def log_stream(websocket: WebSocket, token: str | None = Query(default=None)) -> None:
    """Real-time стрим логов бота через WebSocket."""
    if not await _authenticate_ws(websocket, token):
        return

    await websocket.accept()
    channel = LOGS_CHANNEL
    pubsub = None
    try:
        try:
            redis = get_redis_client()
            pubsub = redis.pubsub()
            await pubsub.subscribe(channel)
        except Exception:
            pubsub = None

        while True:
            if pubsub is not None:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message.get("data"):
                    await websocket.send_text(message["data"])
            else:
                for local_message in consume_local_channel(channel):
                    await websocket.send_text(local_message)
            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        pass
    finally:
        if pubsub is not None:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
