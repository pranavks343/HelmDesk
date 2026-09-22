"""c24: defer=True. Mechanism: merge_sources runs exactly once after every fan-out branch
finishes, including the uneven forum branch (which takes an extra rerank_forum hop) - without
defer=True it would run once for the 1-hop branches and again after forum."""

from supportpilot.context import SupportContext
from supportpilot.subgraphs import kb_agent as kb_mod


def test_merge_sources_runs_exactly_once():
    kb_mod.reset_flaky_counters()
    calls = {"n": 0}
    original = kb_mod.merge_sources

    def counting(state):
        calls["n"] += 1
        return original(state)

    kb_mod.merge_sources = counting
    try:
        kb = kb_mod.build_kb_graph()
        kb.invoke(
            {"query": "sso setup", "rewrite_count": 0},
            {"configurable": {"thread_id": "c24-defer"}},
            context=SupportContext(user_id="u1"),
        )
    finally:
        kb_mod.merge_sources = original
    assert calls["n"] == 1


def test_merge_sources_node_is_registered_with_defer_true():
    kb = kb_mod.build_kb_graph()
    # defer is baked into the node spec at add_node time
    assert kb.builder.nodes["merge_sources"].defer is True
