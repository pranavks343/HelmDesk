"""Motor (async MongoDB) client. Holds `chat_messages`: per-ticket message stream, chosen for
Mongo over Postgres because it's high-write, append-mostly, and schema is loosely structured
(optional embedding field for future KB/semantic search) - a natural fit for a document store
rather than forcing a rigid relational shape onto free-form chat."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from core.config import settings

_client: AsyncIOMotorClient | None = None


def get_mongo_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongo_uri)
    return _client


def get_mongo_db() -> AsyncIOMotorDatabase:
    return get_mongo_client()[settings.mongo_db]


def close_mongo() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


class ChatMessageRepo:
    """Thin repo over the `chat_messages` collection. `db` is injectable for tests (mongomock)."""

    def __init__(self, db: AsyncIOMotorDatabase | None = None) -> None:
        self._db = db or get_mongo_db()

    @property
    def collection(self):
        return self._db["chat_messages"]

    async def add_message(self, ticket_id: str, sender: str, text: str) -> dict[str, Any]:
        doc = {
            "ticket_id": ticket_id,
            "sender": sender,
            "text": text,
            "embedding": None,
            "created_at": datetime.now(UTC),
        }
        await self.collection.insert_one(doc)
        return doc

    async def list_messages(self, ticket_id: str, limit: int = 200) -> list[dict[str, Any]]:
        cursor = self.collection.find({"ticket_id": ticket_id}).sort("created_at", 1).limit(limit)
        return [doc async for doc in cursor]
