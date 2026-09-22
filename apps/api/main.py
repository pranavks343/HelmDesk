from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.redis_client import close_redis, get_redis
from mongo.client import close_mongo
from routers import auth, internal, kb, tickets, ws
from ws.redis_bridge import start_redis_bridge, stop_redis_bridge


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = get_redis()
    bridge_task = start_redis_bridge(redis)
    try:
        yield
    finally:
        await stop_redis_bridge(bridge_task)
        await close_redis()
        close_mongo()


app = FastAPI(title="SupportPilot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tickets.router)
app.include_router(kb.router)
app.include_router(ws.router)
app.include_router(internal.router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
