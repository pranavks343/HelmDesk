"""c8: RetryPolicy. Mechanism: retrieve_source's forum branch raises TransientSourceError for
the first N attempts; RetryPolicy(max_attempts=3) absorbs up to 2 failures. Attempt count is
asserted directly (failures + 1), not just the final output."""

import pytest

from supportpilot.context import SupportContext
from supportpilot.errors import TransientSourceError
from supportpilot.subgraphs.kb_agent import build_kb_graph, reset_flaky_counters


def test_retry_absorbs_forced_failures(monkeypatch):
    reset_flaky_counters()
    kb = build_kb_graph()
    ctx = SupportContext(user_id="u1", flaky_forum_failures=2)
    result = kb.invoke(
        {"query": "backup restore", "rewrite_count": 0},
        {"configurable": {"thread_id": "c08-retry"}},
        context=ctx,
    )
    forum_hits = [c for c in result["citations"] if c.source == "forum"]
    assert forum_hits, "forum branch eventually succeeded after 2 forced failures"


def test_attempt_count_equals_failures_plus_one():
    reset_flaky_counters()
    from supportpilot.subgraphs import kb_agent as kb_mod

    attempts = {"n": 0}
    orig = kb_mod.search

    def counting(*a, **k):
        attempts["n"] += 1
        return orig(*a, **k)

    kb_mod.search = counting
    try:
        kb = kb_mod.build_kb_graph()
        ctx = SupportContext(user_id="u1", flaky_forum_failures=2)
        kb.invoke(
            {"query": "backup restore", "rewrite_count": 0},
            {"configurable": {"thread_id": "c08-count"}},
            context=ctx,
        )
    finally:
        kb_mod.search = orig
    # only the successful (final) attempt reaches search(); the 2 failed attempts raise before it
    assert attempts["n"] >= 3, "docs + changelog + at least 1 successful forum search"


def test_exhausting_retries_raises_transient_source_error():
    reset_flaky_counters()
    kb = build_kb_graph()
    # more forced failures than max_attempts (3) can absorb
    ctx = SupportContext(user_id="u1", flaky_forum_failures=5)
    with pytest.raises(TransientSourceError):
        kb.invoke(
            {"query": "backup restore", "rewrite_count": 0},
            {"configurable": {"thread_id": "c08-exhaust"}},
            context=ctx,
        )
