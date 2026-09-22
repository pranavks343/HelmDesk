import pytest
from pydantic import ValidationError

from supportpilot.schemas import (
    Citation,
    ExtractedMemories,
    GradeResult,
    GuardrailVerdict,
    MemoryFact,
    RefundProposal,
    RewrittenQuery,
    RouteDecision,
)


def test_route_decision_confidence_bounds():
    RouteDecision(next="kb_agent", confidence=0.0, reason="r")
    RouteDecision(next="kb_agent", confidence=1.0, reason="r")
    with pytest.raises(ValidationError):
        RouteDecision(next="kb_agent", confidence=1.5, reason="r")
    with pytest.raises(ValidationError):
        RouteDecision(next="kb_agent", confidence=-0.1, reason="r")


def test_route_decision_rejects_unknown_destination():
    with pytest.raises(ValidationError):
        RouteDecision(next="not_a_real_agent", confidence=0.5, reason="r")


def test_grade_result_optional_missing():
    g = GradeResult(relevant=True, grounded=True)
    assert g.missing is None


def test_rewritten_query_requires_query():
    with pytest.raises(ValidationError):
        RewrittenQuery()


def test_citation_source_literal():
    Citation(doc_id="x", source="docs", title="T", score=0.5, snippet="s")
    with pytest.raises(ValidationError):
        Citation(doc_id="x", source="wiki", title="T", score=0.5, snippet="s")


def test_refund_proposal_amount_non_negative():
    RefundProposal(invoice_id="INV-1", amount=0.0, currency="USD", reason="r", auto_approvable=True)
    with pytest.raises(ValidationError):
        RefundProposal(invoice_id="INV-1", amount=-5.0, currency="USD", reason="r", auto_approvable=True)


def test_refund_proposal_currency_literal():
    with pytest.raises(ValidationError):
        RefundProposal(invoice_id="INV-1", amount=5.0, currency="GBP", reason="r", auto_approvable=True)


def test_memory_fact_category_literal():
    MemoryFact(text="t", category="preference")
    with pytest.raises(ValidationError):
        MemoryFact(text="t", category="not_a_category")


def test_extracted_memories_defaults_to_list():
    em = ExtractedMemories(facts=[])
    assert em.facts == []


def test_guardrail_verdict_shape():
    v = GuardrailVerdict(allowed=True, flags=[], redacted_text="hi")
    assert v.allowed and v.flags == [] and v.redacted_text == "hi"
