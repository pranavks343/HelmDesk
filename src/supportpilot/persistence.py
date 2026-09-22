"""Checkpointer factories, plus state/history/replay/fork helpers (c5, c6, c19)."""

from __future__ import annotations

import sqlite3
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from supportpilot import config as cfg_module
from supportpilot.serde import make_serde

_SERDE = make_serde()


def sqlite_checkpointer(path: str | None = None) -> SqliteSaver:
    conn = sqlite3.connect(path or cfg_module.db_path(), check_same_thread=False)
    return SqliteSaver(conn, serde=_SERDE)


async def async_sqlite_checkpointer(path: str | None = None) -> AsyncSqliteSaver:
    import aiosqlite

    conn = await aiosqlite.connect(path or cfg_module.db_path())
    return AsyncSqliteSaver(conn, serde=_SERDE)


def memory_checkpointer() -> InMemorySaver:
    return InMemorySaver(serde=_SERDE)


def show_state(graph: Any, thread_id: str) -> dict[str, Any]:
    cfg: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    snapshot = graph.get_state(cfg)
    return {
        "values": snapshot.values,
        "next": snapshot.next,
        "tasks": [
            {"name": t.name, "interrupts": [i.value for i in t.interrupts]} for t in snapshot.tasks
        ],
        "config": snapshot.config,
    }


def list_history(graph: Any, thread_id: str) -> list[dict[str, Any]]:
    out = []
    cfg: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    for i, snap in enumerate(graph.get_state_history(cfg)):
        out.append(
            {
                "step": i,
                "checkpoint_id": snap.config["configurable"]["checkpoint_id"],
                "next": snap.next,
                "keys": sorted(snap.values.keys()) if isinstance(snap.values, dict) else [],
                "metadata": snap.metadata,
            }
        )
    return out


def _cfg(thread_id: str, checkpoint_id: str) -> RunnableConfig:
    # SqliteSaver.put_writes indexes on checkpoint_ns and KeyErrors without it - always set it
    # explicitly (the root namespace is "") rather than relying on it being filled in.
    return {"configurable": {"thread_id": thread_id, "checkpoint_ns": "", "checkpoint_id": checkpoint_id}}


def replay(graph: Any, thread_id: str, checkpoint_id: str, **kwargs: Any) -> Any:
    return graph.invoke(None, _cfg(thread_id, checkpoint_id), **kwargs)


def fork(
    graph: Any,
    thread_id: str,
    checkpoint_id: str,
    values: dict[str, Any],
    as_node: str | None = None,
    **kwargs: Any,
) -> Any:
    new_cfg = graph.update_state(_cfg(thread_id, checkpoint_id), values, as_node=as_node)
    return graph.invoke(None, new_cfg, **kwargs)
