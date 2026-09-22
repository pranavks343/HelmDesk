"""c23: CachePolicy. Mechanism: retrieve_source is cached by (source, normalized query); an
identical repeat query skips the retriever entirely; dropping the normaliser would mean
"SSO setup" and "sso setup" never hit the same cache key."""

from supportpilot.context import SupportContext
from supportpilot.retrieval.tfidf import SEARCH_CALLS, normalize
from supportpilot.subgraphs.kb_agent import build_kb_graph, reset_flaky_counters
from tests.conftest import thread_cfg


def test_identical_query_is_a_cache_hit():
    reset_flaky_counters()
    kb = build_kb_graph()
    ctx = SupportContext(user_id="u1", flaky_forum_failures=0)
    SEARCH_CALLS.clear()
    kb.invoke({"query": "webhook signature", "rewrite_count": 0}, thread_cfg("c23-a"), context=ctx)
    before = dict(SEARCH_CALLS)
    kb.invoke({"query": "webhook signature", "rewrite_count": 0}, thread_cfg("c23-b"), context=ctx)
    assert SEARCH_CALLS["docs"] == before["docs"], "second identical query did not hit the retriever"


def test_cache_key_uses_the_normalizer():
    assert normalize("How do Webhooks Work?!") == normalize("how do webhooks work")


def test_different_source_is_a_different_cache_key():
    reset_flaky_counters()
    kb = build_kb_graph()
    ctx = SupportContext(user_id="u1", flaky_forum_failures=0)
    SEARCH_CALLS.clear()
    kb.invoke({"query": "webhooks", "rewrite_count": 0}, thread_cfg("c23-c"), context=ctx)
    # all three sources were actually queried (not short-circuited by a shared cache key)
    assert SEARCH_CALLS["docs"] >= 1 and SEARCH_CALLS["forum"] >= 1 and SEARCH_CALLS["changelog"] >= 1
