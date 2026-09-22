"""compose_reply: the single convergence point that renders the customer-facing reply (c22)."""

from __future__ import annotations

from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

from supportpilot.context import SupportContext
from supportpilot.llm.factory import get_gateway
from supportpilot.memory.short_term import llm_view
from supportpilot.state import ParentState

UNCERTAINTY_PHRASE = "I'm not fully certain this is correct"


def _build_blob(state: ParentState) -> str:
    if edited := (state.get("review") or {}).get("edited_reply"):
        return str(edited)

    route = state.get("route")
    route_next = route.next if route else state.get("active_agent")

    if route_next == "fallback" or state.get("low_confidence") and not state.get("citations"):
        parts = [
            "I'm sorry, I wasn't able to handle this request with full confidence.",
            UNCERTAINTY_PHRASE + ".",
            f"A human specialist will follow up on {state.get('query') or 'your message'!r} shortly.",
        ]
        return " ".join(parts)

    if (refund := state.get("refund")) is not None:
        review = state.get("review") or {}
        if review.get("decision") == "reject":
            return (
                "We reviewed your refund request and are not able to approve it at this time. "
                "A specialist will follow up with more detail."
            )
        amount_line = (
            f"${refund.amount:.2f}" if refund.currency == "USD" else f"{refund.amount} {refund.currency}"
        )
        return (
            f"Good news - your refund of {amount_line} for invoice {refund.invoice_id} has been "
            f"approved and processed."
        )

    if draft := state.get("draft_answer"):
        suffix = f" {UNCERTAINTY_PHRASE}." if state.get("low_confidence") else ""
        return draft + suffix

    # tech agent / greetings: the last AI message already carries the answer.
    for m in reversed(state.get("messages", [])):
        if isinstance(m, AIMessage) and m.content:
            return str(m.content)
    return "Thanks for reaching out - how can I help?"


def compose_reply(state: ParentState, runtime: Runtime[SupportContext]) -> dict:
    blob = _build_blob(state)

    if (state.get("review") or {}).get("edited_reply"):
        text = blob
    else:
        gateway = get_gateway(runtime.context)
        view = llm_view(
            state.get("messages", []),
            state.get("summary", ""),
            state.get("recalled_facts", []),
            max_tokens=runtime.context.max_context_tokens,
        )
        ai = gateway.compose_reply(view, blob)
        text = str(ai.content)

    return {
        "final_answer": text,
        "messages": [AIMessage(content=text)],
        "audit": ["reply composed"],
    }
