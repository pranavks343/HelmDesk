"""memory/store.py: namespaces + backend selection (c11, c21)."""

from __future__ import annotations

from langgraph.store.sqlite import SqliteStore

from supportpilot.memory.store import build_store, digest_namespace, facts_namespace, profile_namespace


def test_namespaces_are_scoped_tuples():
    assert profile_namespace("u1") == ("users", "u1", "profile")
    assert facts_namespace("u1") == ("users", "u1", "facts")
    assert digest_namespace("2026-01-01") == ("digests", "2026-01-01")


def test_build_store_memory_backend():
    store = build_store("memory")
    store.put(profile_namespace("u1"), "profile", {"x": 1})
    assert store.get(profile_namespace("u1"), "profile").value == {"x": 1}


def test_build_store_sqlite_backend_uses_configured_path(tmp_path, monkeypatch):
    db_path = str(tmp_path / "store_test.db")
    monkeypatch.setenv("SUPPORTPILOT_STORE_DB", db_path)
    store = build_store("sqlite")
    assert isinstance(store, SqliteStore)
    store.put(profile_namespace("u1"), "profile", {"plan_tier": "pro"})
    assert store.get(profile_namespace("u1"), "profile").value == {"plan_tier": "pro"}
