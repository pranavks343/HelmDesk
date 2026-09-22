"""manage_context: trim old messages into a rolling summary once the thread gets long (c2, c20)."""

from __future__ import annotations

from langchain_core.messages import RemoveMessage
from langgraph.runtime import Runtime

from supportpilot.context import SupportContext
from supportpilot.llm.factory import get_gateway
from supportpilot.memory.short_term import keep_tail_boundary
from supportpilot.state import ParentState

KEEP_LAST = 4


def manage_context(state: ParentState, runtime: Runtime[SupportContext]) -> dict:
    messages = state.get("messages", [])
    ctx = runtime.context
    if len(messages) <= ctx.summarize_after_messages:
        return {}

    cut = keep_tail_boundary(messages, KEEP_LAST)
    if cut <= 0:
        return {}

    to_drop = messages[:cut]
    gateway = get_gateway(ctx)
    new_summary = gateway.summarize(state.get("summary", ""), to_drop)

    return {
        "summary": new_summary,
        "messages": [RemoveMessage(id=m.id) for m in to_drop if m.id is not None],
        "audit": [f"summarized {len(to_drop)} messages"],
    }
