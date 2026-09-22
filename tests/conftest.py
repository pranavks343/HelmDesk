"""Shared pytest fixtures: isolated ledgers, cleared caches, fresh in-memory graphs."""

from __future__ import annotations

from pathlib import Path

import pytest
from langgraph.cache.memory import InMemoryCache
from langgraph.checkpoint.memory import InMemorySaver

from supportpilot import crash
from supportpilot.context import SupportContext
from supportpilot.graph import build_graph
from supportpilot.llm.factory import get_gateway
from supportpilot.memory.store import build_store
from supportpilot.serde import make_serde
from supportpilot.subgraphs.kb_agent import reset_flaky_counters


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Runs around every test: isolated refund ledger, cleared caches/counters."""
    monkeypatch.setenv("SUPPORTPILOT_LEDGER", str(tmp_path / "ledger.json"))
    monkeypatch.delenv("SUPPORTPILOT_CRASH_AFTER", raising=False)
    get_gateway.cache_clear()
    reset_flaky_counters()
    crash.reset()
    yield


@pytest.fixture
def store():
    return build_store("memory")


@pytest.fixture
def graph(store):
    return build_graph(
        checkpointer=InMemorySaver(serde=make_serde()),
        store=store,
        cache=InMemoryCache(serde=make_serde()),
    )


@pytest.fixture
def ctx_factory():
    def _make(**kwargs):
        kwargs.setdefault("user_id", "u_test")
        return SupportContext(**kwargs)

    return _make


@pytest.fixture
def ctx(ctx_factory):
    return ctx_factory()


def thread_cfg(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}
