"""load_memory, save_memory (c11, c21, c25)."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime
from langgraph.store.base import BaseStore

from supportpilot.context import SupportContext
from supportpilot.llm.factory import get_gateway
from supportpilot.memory.store import facts_namespace, profile_namespace
from supportpilot.state import ParentState

DEDUPE_SCORE = 0.9


def _require_store(runtime: Runtime[SupportContext]) -> BaseStore:
    if runtime.store is None:
        raise RuntimeError("this graph must be compiled with a store (see graph.build_graph)")
    return runtime.store


def load_memory(state: ParentState, runtime: Runtime[SupportContext]) -> dict:
    store = _require_store(runtime)
    uid = runtime.context.user_id
    profile_item = store.get(profile_namespace(uid), "profile")
    profile = profile_item.value if profile_item else {}

    query = ""
    for m in reversed(state.get("messages", [])):
        if isinstance(m, HumanMessage):
            query = str(m.content)
            break

    recalled: list[str] = []
    if query:
        hits = store.search(facts_namespace(uid), query=query, limit=3)
        recalled = [h.value.get("text", "") for h in hits if h.value.get("text")]

    return {"profile": profile, "recalled_facts": recalled}


def save_memory(state: ParentState, runtime: Runtime[SupportContext]) -> dict:
    store = _require_store(runtime)
    uid = runtime.context.user_id
    gateway = get_gateway(runtime.context)
    recent = state.get("messages", [])[-6:]

    extracted = gateway.extract_memories(recent)
    saved = 0
    for fact in extracted.facts:
        existing = store.search(facts_namespace(uid), query=fact.text, limit=1)
        if existing and existing[0].score is not None and existing[0].score >= DEDUPE_SCORE:
            continue
        store.put(facts_namespace(uid), str(uuid_fact(fact.text)), {
            "text": fact.text,
            "category": fact.category,
        })
        saved += 1

    profile_item = store.get(profile_namespace(uid), "profile")
    profile: dict[str, Any] = dict(profile_item.value) if profile_item else {"ticket_count": 0}
    profile["plan_tier"] = runtime.context.plan_tier
    if route := state.get("route"):
        profile["last_topic"] = route.next
    profile["ticket_count"] = profile.get("ticket_count", 0) + 1
    store.put(profile_namespace(uid), "profile", profile)

    return {"audit": [f"memory saved ({saved} new facts)"]}


def uuid_fact(text: str) -> str:
    import hashlib

    return hashlib.sha1(text.encode()).hexdigest()[:16]
