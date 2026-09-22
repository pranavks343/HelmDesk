"""supervisor + fallback (c4, c12, c15, c16, c27)."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime
from langgraph.types import Command

from supportpilot.config import ROUTE_CONFIDENCE_FLOOR, SUPERVISOR_MAX_HOPS, SUPERVISOR_MIN_REMAINING
from supportpilot.context import SupportContext
from supportpilot.llm.factory import get_gateway
from supportpilot.memory.short_term import llm_view
from supportpilot.schemas import RouteDecision
from supportpilot.state import ParentState

# Deterministic rule-based fallback router (the "workflow" half of the workflow-vs-agent
# contrast, c12): used whenever the LLM's structured route is low-confidence.
_BILLING_WORDS = ("refund", "charge", "charged", "invoice", "billing", "billed", "payment")
_TECH_WORDS = ("error", "outage", "down", "status", "order", "bug", "crash")
_KB_WORDS = ("how", "what", "why", "setup", "configure", "docs")


def _rule_based_route(text: str) -> RouteDecision:
    low = text.lower()
    if any(w in low for w in _BILLING_WORDS):
        return RouteDecision(next="billing_agent", confidence=0.6, reason="rule: billing keyword")
    if any(w in low for w in _TECH_WORDS):
        return RouteDecision(next="tech_agent", confidence=0.6, reason="rule: technical keyword")
    if any(w in low for w in _KB_WORDS):
        return RouteDecision(next="kb_agent", confidence=0.6, reason="rule: informational keyword")
    return RouteDecision(next="fallback", confidence=0.4, reason="rule: no keyword matched")


def _last_human_text(state: ParentState) -> str:
    for m in reversed(state.get("messages", [])):
        if isinstance(m, HumanMessage):
            return str(m.content)
    return ""


def supervisor(state: ParentState, runtime: Runtime[SupportContext]) -> Command:
    remaining = state.get("remaining_steps")
    if remaining is not None and remaining < SUPERVISOR_MIN_REMAINING:
        return Command(
            update={"audit": ["step budget low"], "budget_exhausted": True}, goto="fallback"
        )

    hops = state.get("hops", 0)
    if hops >= SUPERVISOR_MAX_HOPS:
        return Command(update={"audit": ["hop limit reached"]}, goto="compose_reply")

    if hops > 0:
        # A specialist already ran earlier in this turn (billing_agent never returns here - it
        # Command(goto=...)s straight to human_review/execute_refund). Detect whether it produced
        # a final answer so we don't ping-pong back into the same agent for no reason.
        kb_done = state.get("grade") is not None
        messages = state.get("messages", [])
        last = messages[-1] if messages else None
        tech_done = isinstance(last, AIMessage) and not last.tool_calls and last.content
        if kb_done or tech_done:
            return Command(update={"audit": ["specialist finished"]}, goto="compose_reply")

    ctx = runtime.context
    gateway = get_gateway(ctx)
    view = llm_view(
        state.get("messages", []),
        state.get("summary", ""),
        state.get("recalled_facts", []),
        max_tokens=ctx.max_context_tokens,
    )
    decision = gateway.route(view, state.get("summary", ""), state.get("profile", {}))

    text = _last_human_text(state)
    if decision.confidence < ROUTE_CONFIDENCE_FLOOR:
        decision = _rule_based_route(text)

    return Command(
        update={
            "route": decision,
            "active_agent": decision.next,
            "hops": 1,
            "query": text,
        },
        goto=decision.next,
    )


def fallback(state: ParentState) -> dict:
    """Deterministic, no LLM call of its own: flags the turn low-confidence and audit-trails it,
    then hands off to ``compose_reply`` (fixed edge) which renders the actual apology text -
    that keeps every customer-facing reply flowing through the same token-streamed node and
    through the output guardrail."""
    return {"low_confidence": True, "audit": ["fallback triggered"]}
