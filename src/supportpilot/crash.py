"""Crash-injection hook for the resume-after-crash demo (c5, c19).

Set ``SUPPORTPILOT_CRASH_AFTER=<node_name>`` and the named node raises ``SimulatedCrash`` the
*first* time it is about to run, but only after checking a module-level "already ran once"
marker keyed by thread id - so the crash happens after upstream nodes have been checkpointed, and
re-running with the same thread_id resumes from the last good checkpoint instead of re-raising.
"""

from __future__ import annotations

import os

from langgraph.config import get_config

from supportpilot.errors import SimulatedCrash

_CRASHED_THREADS: set[str] = set()


def reset() -> None:
    _CRASHED_THREADS.clear()


def maybe_crash(node_name: str) -> None:
    target = os.environ.get("SUPPORTPILOT_CRASH_AFTER")
    if target != node_name:
        return
    try:
        thread_id = str(get_config().get("configurable", {}).get("thread_id", ""))
    except RuntimeError:
        return
    key = f"{thread_id}:{node_name}"
    if key in _CRASHED_THREADS:
        return  # already crashed once for this thread/node; let it proceed on resume
    _CRASHED_THREADS.add(key)
    raise SimulatedCrash(f"simulated crash after {node_name}")
