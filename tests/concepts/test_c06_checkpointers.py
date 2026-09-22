"""c6: SqliteSaver vs InMemorySaver. Mechanism: the same thread run against two separately
constructed graphs survives with SqliteSaver (shared file) but not with InMemorySaver (in-process
only)."""

import sqlite3

from langgraph.cache.memory import InMemoryCache
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from supportpilot.graph import build_graph
from supportpilot.persistence import _SERDE
from supportpilot.serde import make_serde


def test_sqlite_saver_persists_across_graph_instances(tmp_path, store, ctx):
    db = str(tmp_path / "c06.db")
    cfg = {"configurable": {"thread_id": "c06-sqlite"}}

    g1 = build_graph(
        checkpointer=SqliteSaver(sqlite3.connect(db, check_same_thread=False), serde=_SERDE),
        store=store,
        cache=InMemoryCache(serde=make_serde()),
    )
    g1.invoke({"messages": [("human", "hello")]}, cfg, context=ctx)

    g2 = build_graph(
        checkpointer=SqliteSaver(sqlite3.connect(db, check_same_thread=False), serde=_SERDE), store=store
    )
    assert g2.get_state(cfg).values.get("final_answer")


def test_in_memory_saver_does_not_persist_across_instances(store, ctx):
    cfg = {"configurable": {"thread_id": "c06-memory"}}
    g1 = build_graph(
        checkpointer=InMemorySaver(serde=_SERDE), store=store, cache=InMemoryCache(serde=make_serde())
    )
    g1.invoke({"messages": [("human", "hello")]}, cfg, context=ctx)

    g2 = build_graph(checkpointer=InMemorySaver(serde=_SERDE), store=store)
    assert not g2.get_state(cfg).values.get("final_answer")
