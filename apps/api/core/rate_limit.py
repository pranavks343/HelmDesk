"""Redis-based fixed-window rate limiting per IP/user, used on auth + ticket-create endpoints."""

from __future__ import annotations

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

from core.redis_client import get_redis


def _client_key(request: Request, prefix: str) -> str:
    user = getattr(request.state, "user_id", None)
    identity = user or (request.client.host if request.client else "unknown")
    return f"ratelimit:{prefix}:{identity}"


async def enforce_rate_limit(
    request: Request, prefix: str, limit: int, window_seconds: int = 60, redis: Redis | None = None
) -> None:
    r = redis or get_redis()
    key = _client_key(request, prefix)
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, window_seconds)
    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"rate limit exceeded: {limit} requests per {window_seconds}s",
        )
