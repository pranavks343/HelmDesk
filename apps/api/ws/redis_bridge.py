"""Background task: subscribes to Redis pub/sub and relays events to WebSocket clients.

This is the "Redis -> FastAPI -> WS -> React" leg of the architecture diagram in agents.md §2.
Runs once per `api` process, started in the FastAPI lifespan (see main.py).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging

from redis.asyncio import Redis

from core.redis_client import CHANNEL_TICKET_MESSAGE, CHANNEL_TICKET_UPDATED
from ws.manager import manager

logger = logging.getLogger(__name__)


async def run_redis_bridge(redis: Redis) -> None:
    pubsub = redis.pubsub()
    await pubsub.subscribe(CHANNEL_TICKET_UPDATED, CHANNEL_TICKET_MESSAGE)
    try:
        async for raw in pubsub.listen():
            if raw["type"] != "message":
                continue
            try:
                event = json.loads(raw["data"])
            except (TypeError, ValueError):
                logger.warning("redis_bridge: dropped malformed event: %r", raw["data"])
                continue
            ticket_id = event.get("ticket_id")
            if not ticket_id:
                continue
            await manager.broadcast(ticket_id, event)
    finally:
        await pubsub.unsubscribe(CHANNEL_TICKET_UPDATED, CHANNEL_TICKET_MESSAGE)
        await pubsub.aclose()


def start_redis_bridge(redis: Redis) -> asyncio.Task:
    task = asyncio.create_task(run_redis_bridge(redis))
    return task


async def stop_redis_bridge(task: asyncio.Task) -> None:
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
