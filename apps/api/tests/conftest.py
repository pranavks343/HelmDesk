"""Test fixtures: sqlite in place of Postgres, mongomock in place of Mongo, fakeredis in place of
Redis - no real infra needed to run `pytest` (matches the "deterministic, offline" spirit carried
over from the previous build, per §11)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from core import redis_client
from core.db import Base, get_db
from models import ticket, user  # noqa: F401 - import registers tables on Base.metadata
from mongo import client as mongo_client_module


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session


@pytest.fixture
def mongo_db():
    return AsyncMongoMockClient()["supportpilot_test"]


@pytest_asyncio.fixture
async def fake_redis():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()


@pytest_asyncio.fixture
async def client(db_engine, mongo_db, fake_redis, monkeypatch):
    from main import app

    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _get_db_override():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db_override
    monkeypatch.setattr(redis_client, "_redis", fake_redis)
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake_redis)
    monkeypatch.setattr(mongo_client_module, "get_mongo_db", lambda: mongo_db)

    # Patch the modules that imported get_redis/get_mongo_db directly by name.
    import routers.tickets as tickets_module

    monkeypatch.setattr(tickets_module, "get_redis", lambda: fake_redis)

    import mongo.client as mongo_module

    def _init_with_mock_db(self, db=None):
        self._db = mongo_db

    monkeypatch.setattr(mongo_module.ChatMessageRepo, "__init__", _init_with_mock_db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
