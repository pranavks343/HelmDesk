"""Billing subgraph with its own private, disjoint schema (c17)."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from supportpilot.context import SupportContext
from supportpilot.llm.factory import get_gateway
from supportpilot.state import BillingState
from supportpilot.tools.crm import load_crm


def load_account(state: BillingState) -> dict:
    crm = load_crm()
    customer = crm["customers"].get(state["customer_id"], {})
    invoices = [
        crm["invoices"][i] | {"invoice_id": i} for i in customer.get("invoices", []) if i in crm["invoices"]
    ]
    account = {
        "customer_id": state["customer_id"],
        "name": customer.get("name", "unknown"),
        "plan_tier": customer.get("plan_tier", "free"),
        "invoices": invoices,
    }
    return {"account": account, "invoices": invoices}


def assess_refund(state: BillingState, runtime: Runtime[SupportContext]) -> dict:
    gateway = get_gateway(runtime.context)
    proposal = gateway.assess_refund(state.get("account", {}), state.get("complaint", ""))
    # Auto-approval threshold is a runtime policy, not something the gateway should hardcode.
    proposal = proposal.model_copy(
        update={"auto_approvable": proposal.amount <= runtime.context.refund_auto_approve_limit}
    )
    return {"proposal": proposal}


def build_billing_graph() -> CompiledStateGraph[BillingState, SupportContext, BillingState, BillingState]:
    g = StateGraph(BillingState, context_schema=SupportContext)
    g.add_node("load_account", load_account)
    g.add_node("assess_refund", assess_refund)
    g.add_edge(START, "load_account")
    g.add_edge("load_account", "assess_refund")
    g.add_edge("assess_refund", END)
    return g.compile()
