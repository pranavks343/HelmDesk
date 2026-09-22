"""Long-term memory store: exact profile + semantic facts, namespaced per user (c11, c21)."""

from __future__ import annotations

import sqlite3
from typing import Literal

from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

from supportpilot import config as cfg_module
from supportpilot.retrieval.embeddings import HashingEmbeddings

_INDEX = {"embed": HashingEmbeddings(), "dims": 256, "fields": ["text"]}


def profile_namespace(user_id: str) -> tuple[str, str, str]:
    return ("users", user_id, "profile")


def facts_namespace(user_id: str) -> tuple[str, str, str]:
    return ("users", user_id, "facts")


def digest_namespace(date: str) -> tuple[str, str]:
    return ("digests", date)


def build_store(backend: Literal["memory", "sqlite"] = "memory") -> BaseStore:
    if backend == "sqlite":
        try:
            from langgraph.store.sqlite import SqliteStore

            # isolation_level=None (autocommit): SqliteStore.setup() runs its migration DDL via
            # conn.executescript(...), which under Python's default (deferred) isolation level
            # leaves an implicit transaction open - the store's own next `.put()`/`.get()` then
            # fails issuing its own `BEGIN` ("cannot start a transaction within a transaction").
            # Autocommit mode lets the store manage its own transactions exclusively, matching
            # what SqliteSaver's connections already do implicitly (see persistence.py).
            conn = sqlite3.connect(cfg_module.store_db_path(), check_same_thread=False, isolation_level=None)
            store = SqliteStore(conn, index=_INDEX)  # type: ignore[arg-type]
            store.setup()
            return store
        except Exception:
            # SqliteStore's vector index support wasn't verified for this install; fall back.
            # See docs/API_NOTES.md.
            return InMemoryStore(index=_INDEX)  # type: ignore[arg-type]
    return InMemoryStore(index=_INDEX)  # type: ignore[arg-type]
