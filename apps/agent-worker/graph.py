"""LangGraph agent state machine (agents.md §8): classify -> search_kb -> draft_reply -> decide.

Why a graph over a single prompt: this is multi-step (classify, retrieve, draft, decide) with a
real tool call (KB search) and a genuine conditional branch (a low-confidence classification skips
straight to escalation rather than wasting a draft call on a ticket we don't understand) - a
single prompt can't express "call this tool, then branch on a threshold" as a reviewable,
independently-testable pipeline the way a small graph can.

State/memory: `TicketAgentState` is the only thing passed between nodes - each node reads what it
needs and returns a partial update (LangGraph merges it in), so nodes stay independently testable
with a plain dict in, dict out. Nothing here is a class or held in module state.

Fallback: `classify`/`draft_reply` catch any exception from the LLM gateway (a real model over the
network can time out or error) and degrade to a safe, clearly-marked default (confidence 0.0)
rather than crashing the whole ticket triage - `decide` treats a 0.0-confidence ticket the same as
any other low-confidence one: escalate to a human, never silently auto-resolve on a guess.
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from config import settings
from llm import ClassifyResult, DraftResult, LLMGateway, get_gateway
from tools import KBHit, kb_search

LOW_CONFIDENCE_SKIP_DRAFT = 0.35


class TicketAgentState(TypedDict, total=False):
    ticket_id: str
    title: str
    context_messages: list[str]

    category: str
    priority: str
    classify_confidence: float

    kb_hits: list[KBHit]

    draft_text: str
    draft_confidence: float

    auto_resolve: bool
    escalation_reason: str


def _classify_node(gateway: LLMGateway):
    def node(state: TicketAgentState) -> dict:
        try:
            result: ClassifyResult = gateway.classify(
                state["title"], state.get("context_messages", [])
            )
        except Exception as exc:  # noqa: BLE001 - a flaky/timed-out LLM call must not crash triage
            return {
                "category": "general",
                "priority": "medium",
                "classify_confidence": 0.0,
                "escalation_reason": f"classify failed: {exc}",
            }
        return {
            "category": result.category,
            "priority": result.priority,
            "classify_confidence": result.confidence,
        }

    return node


def _search_kb_node(state: TicketAgentState) -> dict:
    query = " ".join([state.get("title", ""), *state.get("context_messages", [])])
    return {"kb_hits": kb_search(query)}


def _draft_reply_node(gateway: LLMGateway):
    def node(state: TicketAgentState) -> dict:
        try:
            result: DraftResult = gateway.draft_reply(
                state["title"], state.get("context_messages", []), state.get("kb_hits", [])
            )
        except Exception as exc:  # noqa: BLE001 - same fallback principle as classify
            return {
                "draft_text": "A specialist will follow up on this shortly.",
                "draft_confidence": 0.0,
                "escalation_reason": f"draft failed: {exc}",
            }
        return {"draft_text": result.text, "draft_confidence": result.confidence}

    return node


def _decide_node(state: TicketAgentState) -> dict:
    classify_conf = state.get("classify_confidence", 0.0)
    draft_conf = state.get("draft_confidence", 0.0)
    # both stages have to be confident - a great draft on a misclassified ticket is still wrong.
    combined = min(classify_conf, draft_conf) if "draft_confidence" in state else classify_conf * 0.5
    auto_resolve = combined >= settings.auto_resolve_confidence
    update: dict = {"auto_resolve": auto_resolve}
    if not auto_resolve and "escalation_reason" not in state:
        update["escalation_reason"] = f"confidence {combined:.2f} below threshold"
    return update


def _route_after_classify(state: TicketAgentState) -> str:
    if state.get("classify_confidence", 0.0) < LOW_CONFIDENCE_SKIP_DRAFT:
        return "decide"
    return "search_kb"


def build_graph(gateway: LLMGateway | None = None):
    gw = gateway or get_gateway(settings.llm_provider, settings.anthropic_api_key, settings.anthropic_model)

    g = StateGraph(TicketAgentState)
    g.add_node("classify", _classify_node(gw))
    g.add_node("search_kb", _search_kb_node)
    g.add_node("draft_reply", _draft_reply_node(gw))
    g.add_node("decide", _decide_node)

    g.add_edge(START, "classify")
    g.add_conditional_edges("classify", _route_after_classify, ["search_kb", "decide"])
    g.add_edge("search_kb", "draft_reply")
    g.add_edge("draft_reply", "decide")
    g.add_edge("decide", END)

    return g.compile()
