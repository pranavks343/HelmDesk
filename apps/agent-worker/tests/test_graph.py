"""Deterministic graph-transition tests (mocked LLM gateway) per agents.md §11: "agent-worker:
mock LLM calls, test graph transitions deterministically"."""

from graph import build_graph
from llm import ClassifyResult, DraftResult


class StubGateway:
    def __init__(self, classify_result: ClassifyResult, draft_result: DraftResult | None = None) -> None:
        self._classify_result = classify_result
        self._draft_result = draft_result

    def classify(self, title, context):
        return self._classify_result

    def draft_reply(self, title, context, kb_hits):
        if self._draft_result is None:
            raise AssertionError("draft_reply should not have been called")
        return self._draft_result


def test_high_confidence_path_auto_resolves():
    gateway = StubGateway(
        ClassifyResult(category="billing", priority="low", confidence=0.95),
        DraftResult(text="refund processed", confidence=0.9),
    )
    graph = build_graph(gateway)
    result = graph.invoke({"ticket_id": "t1", "title": "refund please", "context_messages": []})

    assert result["category"] == "billing"
    assert result["auto_resolve"] is True
    assert "kb_hits" in result  # search_kb ran
    assert result["draft_text"] == "refund processed"


def test_low_confidence_classification_skips_kb_and_draft():
    """The conditional edge: classify_confidence below LOW_CONFIDENCE_SKIP_DRAFT routes straight
    to `decide`, skipping search_kb/draft_reply entirely - proven by the stub raising if
    draft_reply is called, and kb_hits never appearing in the result."""
    gateway = StubGateway(ClassifyResult(category="general", priority="low", confidence=0.1))
    graph = build_graph(gateway)
    result = graph.invoke({"ticket_id": "t2", "title": "asdkjasd", "context_messages": []})

    assert result["auto_resolve"] is False
    assert "kb_hits" not in result
    assert "draft_text" not in result
    assert "escalation_reason" in result


def test_medium_confidence_escalates_not_auto_resolves():
    gateway = StubGateway(
        ClassifyResult(category="technical", priority="medium", confidence=0.6),
        DraftResult(text="try restarting", confidence=0.6),
    )
    graph = build_graph(gateway)
    result = graph.invoke({"ticket_id": "t3", "title": "something is slow", "context_messages": []})

    assert result["auto_resolve"] is False
    assert result["draft_text"] == "try restarting"


def test_classify_failure_degrades_gracefully_and_escalates():
    class FailingGateway:
        def classify(self, title, context):
            raise TimeoutError("upstream LLM timed out")

        def draft_reply(self, title, context, kb_hits):  # pragma: no cover - should not be reached
            raise AssertionError("should not draft after a classify failure escalation")

    graph = build_graph(FailingGateway())
    result = graph.invoke({"ticket_id": "t4", "title": "anything", "context_messages": []})

    assert result["category"] == "general"
    assert result["classify_confidence"] == 0.0
    assert result["auto_resolve"] is False
    assert "classify failed" in result["escalation_reason"]


def test_draft_failure_degrades_gracefully_and_escalates():
    gateway = StubGateway(ClassifyResult(category="billing", priority="high", confidence=0.9))

    def failing_draft(title, context, kb_hits):
        raise ConnectionError("network blip")

    gateway.draft_reply = failing_draft  # type: ignore[method-assign]

    graph = build_graph(gateway)
    result = graph.invoke({"ticket_id": "t5", "title": "refund", "context_messages": []})

    assert result["draft_confidence"] == 0.0
    assert result["auto_resolve"] is False
    assert "draft failed" in result["escalation_reason"]


def test_end_to_end_with_real_fake_llm_and_kb():
    """Full pipeline, real FakeLLM + real kb_search - the default offline configuration."""
    graph = build_graph()
    result = graph.invoke(
        {"ticket_id": "t6", "title": "how do I set up sso with okta", "context_messages": []}
    )
    assert result["category"] == "technical"
    assert result["kb_hits"]
    assert result["kb_hits"][0].doc_id == "sso-setup"
    assert result["draft_text"]
