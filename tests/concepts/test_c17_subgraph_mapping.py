"""c17: subgraph with a different schema + explicit mapping. Mechanism: BillingState is disjoint
from ParentState; to_billing/from_billing bridge them explicitly (no shared keys/reducers)."""

from supportpilot.context import SupportContext
from supportpilot.nodes.billing_wrapper import from_billing, to_billing
from supportpilot.state import BillingState, ParentState
from supportpilot.subgraphs.billing_agent import build_billing_graph


def test_billing_state_shares_no_keys_with_parent_state():
    assert not (set(BillingState.__annotations__) & set(ParentState.__annotations__))


def test_to_billing_maps_parent_state_into_billing_state():
    ctx = SupportContext(user_id="u_alice")
    parent_state: ParentState = {"query": "I was charged twice"}
    billing_state = to_billing(parent_state, ctx)
    assert billing_state["customer_id"] == "u_alice"
    assert billing_state["complaint"] == "I was charged twice"


def test_from_billing_maps_proposal_back_into_a_parent_update():
    ctx = SupportContext(user_id="u_alice")
    bg = build_billing_graph()
    result = bg.invoke(to_billing({"query": "charged twice"}, ctx), context=ctx)
    update = from_billing(result)
    assert "refund" in update
    assert update["refund"].invoice_id
    assert "billing assessment complete" in update["audit"]
