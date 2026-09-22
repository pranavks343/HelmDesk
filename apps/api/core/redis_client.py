"""Redis: cache + pub/sub event bus + rate limiting.

Pub/sub is the lightweight event bus between `api` and `agent-worker` (§2 of agents.md): `api`
publishes `ticket.created` / `ticket.message`, `agent-worker` triages and publishes
`ticket.updated`, which `api` relays to the browser over the ticket's WebSocket.

Interview note on Redis vs Kafka: pub/sub has no persistence/replay and no consumer groups - fine
here because we don't need at-least-once delivery or multiple independent consumer groups at this
scale. Kafka is the named production upgrade path once fan-out or durability matters.
"""

from __future__ import annotations

from redis.asyncio import Redis

from core.config import settings

CHANNEL_TICKET_CREATED = "ticket.created"
CHANNEL_TICKET_MESSAGE = "ticket.message"
CHANNEL_TICKET_UPDATED = "ticket.updated"

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
