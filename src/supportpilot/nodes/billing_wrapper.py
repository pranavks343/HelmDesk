"""Parent-graph wrapper around the billing subgraph, with explicit schema mapping (c17)."""

from __future__ import annotations

from typing import cast

from langgraph.runtime import Runtime

from supportpilot.context import SupportContext
from supportpilot.state import BillingState, ParentState
from supportpilot.subgraphs.billing_agent import build_billing_graph

_billing_graph = build_billing_graph()


def to_billing(state: ParentState, ctx: SupportContext) -> BillingState:
    complaint = state.get("query") or ""
    return BillingState(
        customer_id=ctx.user_id, complaint=complaint, account={}, invoices=[], proposal=None
    )


def from_billing(result: BillingState) -> dict:
    return {"refund": result.get("proposal"), "audit": ["billing assessment complete"]}


def billing_agent(state: ParentState, runtime: Runtime[SupportContext]) -> dict:
    """A plain node (not a `Command`) on purpose: routing after it is a *conditional edge*
    (`route_after_billing`, in graph.py) rather than baked into a `Command(goto=...)`. That's
    what lets `update_state(..., as_node="billing_agent")` (c19 fork) recompute the branch from a
    forked `refund` value - a `Command`'s goto is opaque to replay and can't be recomputed that
    way; a conditional edge function is re-evaluated against the new state."""
    raw = _billing_graph.invoke(to_billing(state, runtime.context), context=runtime.context)
    return from_billing(cast(BillingState, raw))


def route_after_billing(state: ParentState) -> str:
    refund = state.get("refund")
    return "human_review" if refund is None or not refund.auto_approvable else "execute_refund"
