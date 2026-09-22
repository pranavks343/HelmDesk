"""Trim + rolling summary (c20).

Two distinct mechanisms:
- ``manage_context`` (a node, in nodes/context_nodes.py) *deletes* old messages from state via
  ``RemoveMessage`` once the thread is long, folding them into ``summary`` first. This changes
  what is stored and checkpointed.
- ``llm_view`` (a plain helper, called at every LLM call site) *trims* the model's view of
  ``messages`` with ``trim_messages`` and prepends a system message with the summary and recalled
  facts. This changes only what the model sees for that one call; state is untouched.
"""

from __future__ import annotations

from typing import cast

from langchain_core.messages import AnyMessage, SystemMessage, trim_messages
from langchain_core.messages.utils import count_tokens_approximately

from supportpilot.context import SupportContext


def llm_view(
    messages: list[AnyMessage],
    summary: str = "",
    recalled_facts: list[str] | None = None,
    *,
    max_tokens: int = 1200,
) -> list[AnyMessage]:
    trimmed = cast(
        "list[AnyMessage]",
        trim_messages(
            messages,
            strategy="last",
            max_tokens=max_tokens,
            token_counter=count_tokens_approximately,
            start_on="human",
            include_system=True,
        ),
    )
    facts_str = "; ".join(recalled_facts or [])
    header_parts = []
    if summary:
        header_parts.append(f"Conversation summary so far: {summary}")
    if facts_str:
        header_parts.append(f"Known facts about this customer: {facts_str}")
    if not header_parts:
        return trimmed
    return [SystemMessage(content="\n".join(header_parts)), *trimmed]


def context_view(state: dict, ctx: SupportContext) -> list[AnyMessage]:
    """Convenience wrapper: build the trimmed view from a ParentState-shaped dict + context."""
    return llm_view(
        state.get("messages", []),
        state.get("summary", ""),
        state.get("recalled_facts", []),
        max_tokens=ctx.max_context_tokens,
    )


def keep_tail_boundary(messages: list[AnyMessage], keep_last: int) -> int:
    """Return the index to cut at so we never split an AIMessage(tool_calls) from its
    ToolMessages. ``messages[:cut]`` is safe to remove."""
    if keep_last <= 0 or keep_last >= len(messages):
        return 0
    cut = len(messages) - keep_last
    # If the message right at the cut point is a ToolMessage, walk the cut back to the AIMessage
    # that issued the call that produced it (and any of its siblings).
    while cut > 0 and getattr(messages[cut], "type", None) == "tool":
        cut -= 1
    return cut
