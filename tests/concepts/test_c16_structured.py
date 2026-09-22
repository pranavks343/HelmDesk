"""c16: structured output. Mechanism: gateways return real Pydantic model instances (not raw
dicts/strings); the graph's route/grade/refund decisions are always validated instances."""

from supportpilot.context import SupportContext
from supportpilot.llm.factory import get_gateway
from supportpilot.schemas import GradeResult, RefundProposal, RouteDecision


def test_route_returns_a_validated_route_decision():
    get_gateway.cache_clear()
    gw = get_gateway(SupportContext(user_id="u1"))
    from langchain_core.messages import HumanMessage

    decision = gw.route([HumanMessage(content="how do I set up sso")], "", {})
    assert isinstance(decision, RouteDecision)
    assert 0 <= decision.confidence <= 1


def test_grade_returns_a_validated_grade_result():
    get_gateway.cache_clear()
    gw = get_gateway(SupportContext(user_id="u1"))
    result = gw.grade("q", "a", [])
    assert isinstance(result, GradeResult)


def test_assess_refund_returns_a_validated_refund_proposal():
    get_gateway.cache_clear()
    gw = get_gateway(SupportContext(user_id="u1"))
    proposal = gw.assess_refund(
        {"invoices": [{"invoice_id": "INV-1", "amount": 10.0, "currency": "USD", "duplicate_charge": True}]},
        "charged twice",
    )
    assert isinstance(proposal, RefundProposal)
    assert proposal.amount == 10.0
