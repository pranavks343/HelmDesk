"""c18: sequential interrupts. Mechanism: human_review calls interrupt() twice; resume values are
matched by order (approve/reject first, edited reply second); the node re-runs from the top on
every resume, proven by counting entries."""

from langgraph.types import Command

from tests.conftest import thread_cfg


def test_two_interrupts_resolved_in_order(graph, ctx_factory):
    ctx = ctx_factory(user_id="u_alice")
    cfg = thread_cfg("c18-order")
    graph.invoke({"messages": [("human", "I was charged twice, please refund")]}, cfg, context=ctx)
    snap1 = graph.get_state(cfg)
    assert snap1.tasks[0].interrupts[0].value["type"] == "approve_refund"

    graph.invoke(Command(resume="approve"), cfg, context=ctx)
    snap2 = graph.get_state(cfg)
    assert snap2.tasks[0].interrupts[0].value["type"] == "edit_reply"

    result = graph.invoke(Command(resume="Custom reply text"), cfg, context=ctx)
    assert result["review"] == {"decision": "approve", "edited_reply": "Custom reply text"}
    assert result["final_answer"] == "Custom reply text"


def test_human_review_re_enters_from_the_top_on_every_resume(graph, ctx_factory):
    """The node re-runs from the top on resume (gotcha 1): count entries via a monkeypatched
    counter around the node function itself."""
    from supportpilot.nodes import human_review as hr_mod

    entries = {"n": 0}
    original = hr_mod.human_review

    def counting(*a, **k):
        entries["n"] += 1
        return original(*a, **k)

    hr_mod.human_review = counting
    try:
        import importlib

        import supportpilot.graph as graph_mod

        importlib.reload(graph_mod)
        fresh_graph = graph_mod.build_graph(
            checkpointer=graph.checkpointer, store=graph.store, cache=None
        )
        ctx = ctx_factory(user_id="u_alice")
        cfg = thread_cfg("c18-reentry")
        fresh_graph.invoke({"messages": [("human", "I was charged twice, please refund")]}, cfg, context=ctx)
        fresh_graph.invoke(Command(resume="approve"), cfg, context=ctx)
        fresh_graph.invoke(Command(resume="text"), cfg, context=ctx)
    finally:
        hr_mod.human_review = original
        importlib.reload(graph_mod)

    assert entries["n"] == 3, "human_review ran once per invoke() call (3 total: initial + 2 resumes)"
