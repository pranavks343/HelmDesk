"""c25: runtime context. Mechanism: SupportContext flows through `context=` at invoke time, is
read via `runtime.context` inside nodes, and is never written into state."""

from supportpilot.context import SupportContext
from tests.conftest import thread_cfg


def test_context_drives_behavior_without_polluting_state(graph, ctx_factory):
    ctx = ctx_factory(user_id="u_alice", refund_auto_approve_limit=5.0)
    cfg = thread_cfg("c25-context")
    result = graph.invoke({"messages": [("human", "I was charged twice, please refund")]}, cfg, context=ctx)
    snap = graph.get_state(cfg)
    assert snap.next == ("human_review",), "a low auto-approve limit (context) forced human review"
    for key in ("plan_tier", "llm_provider", "model_name", "refund_auto_approve_limit"):
        assert key not in result, f"{key} is context, must never leak into state"


def test_same_thread_different_context_changes_outcome(graph, ctx_factory):
    cfg1 = thread_cfg("c25-strict")
    graph.invoke(
        {"messages": [("human", "I was charged twice, please refund")]},
        cfg1,
        context=ctx_factory(user_id="u_alice", refund_auto_approve_limit=1.0),
    )
    assert graph.get_state(cfg1).next == ("human_review",)

    cfg2 = thread_cfg("c25-lenient")
    result2 = graph.invoke(
        {"messages": [("human", "I was charged twice, please refund")]},
        cfg2,
        context=ctx_factory(user_id="u_alice", refund_auto_approve_limit=1000.0),
    )
    assert graph.get_state(cfg2).next == ()
    assert result2.get("refund_executed")


def test_context_is_frozen_and_hashable():
    a = SupportContext(user_id="u1")
    b = SupportContext(user_id="u1")
    assert a == b and hash(a) == hash(b)
