"""c13: agentic RAG. Mechanism: kb_agent's grade -> rewrite loop retries up to REWRITE_LIMIT times
when the first answer is ungrounded (fake_behavior="bad_answer"), then succeeds."""

from supportpilot.config import REWRITE_LIMIT
from supportpilot.context import SupportContext
from supportpilot.subgraphs.kb_agent import build_kb_graph
from tests.conftest import thread_cfg


def test_bad_first_answer_triggers_a_rewrite():
    kb = build_kb_graph()
    ctx = SupportContext(user_id="u1", fake_behavior="bad_answer")
    result = kb.invoke(
        {"query": "how do backups work", "rewrite_count": 0}, thread_cfg("c13-rewrite"), context=ctx
    )
    assert result["rewrite_count"] >= 1
    assert result["grade"].relevant and result["grade"].grounded


def test_persistently_bad_answers_flag_low_confidence_and_stop():
    from supportpilot.llm import fake as fake_mod

    kb = build_kb_graph()
    ctx = SupportContext(user_id="u1", fake_behavior="bad_answer")

    # Force every generate_answer call to be "bad" (not just the first) to exercise the rewrite
    # ceiling directly.
    original = fake_mod.FakeGateway.generate_answer

    def always_bad(self, question, citations):
        from langchain_core.messages import AIMessage

        return AIMessage(content=f"guessing.{fake_mod._BAD_ANSWER_MARKER}")

    fake_mod.FakeGateway.generate_answer = always_bad
    try:
        result = kb.invoke(
            {"query": "how do backups work", "rewrite_count": 0}, thread_cfg("c13-ceiling"), context=ctx
        )
    finally:
        fake_mod.FakeGateway.generate_answer = original

    assert result["rewrite_count"] == REWRITE_LIMIT
    assert result["low_confidence"] is True
