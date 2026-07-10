"""Redis helpers с fallback для локальных тестов."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable
from typing import cast

import redis.asyncio as redis

from app.config import get_settings

settings = get_settings()
_memory_store: set[str] = set()
_memory_channels: dict[str, list[str]] = defaultdict(list)
_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


# M-2: TTL для blacklist — максимум время жизни refresh-токена (7 дней)
_BLACKLIST_TTL_SEC = settings.JWT_REFRESH_TTL_DAYS * 86400


async def add_to_blacklist(value: str) -> None:
    try:
        r = get_redis_client()
        key = f"auth:blacklist:{value}"
        await cast(Awaitable[bool | None], r.set(key, "1", ex=_BLACKLIST_TTL_SEC))
    except Exception:
        _memory_store.add(value)


async def is_blacklisted(value: str) -> bool:
    try:
        exists = await cast(
            Awaitable[str | None],
            get_redis_client().get(f"auth:blacklist:{value}"),
        )
        return exists is not None
    except Exception:
        return value in _memory_store


async def publish(channel: str, message: str) -> None:
    try:
        await cast(Awaitable[int], get_redis_client().publish(channel, message))
    except Exception:
        _memory_channels[channel].append(message)


def consume_local_channel(channel: str) -> list[str]:
    messages = list(_memory_channels[channel])
    _memory_channels[channel].clear()
    return messages


# --- Rate limiting ---

_memory_rate: dict[str, list[float]] = defaultdict(list)


async def check_rate_limit(key: str, max_attempts: int, window_sec: int) -> bool:
    """Return True if request is allowed, False if rate-limited."""
    try:
        r = get_redis_client()
        redis_key = f"ratelimit:{key}"
        current = await cast(Awaitable[int | None], r.get(redis_key))
        if current is not None and int(current) >= max_attempts:
            return False
        pipe = r.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, window_sec)
        await cast(Awaitable[list], pipe.execute())
        return True
    except Exception:
        import time
        now = time.time()
        _memory_rate[key] = [t for t in _memory_rate[key] if now - t < window_sec]
        if len(_memory_rate[key]) >= max_attempts:
            return False
        _memory_rate[key].append(now)
        return True


async def reset_rate_limit(key: str) -> None:
    """Reset rate limit counter after successful login."""
    try:
        r = get_redis_client()
        await cast(Awaitable[int], r.delete(f"ratelimit:{key}"))
    except Exception:
        _memory_rate.pop(key, None)
