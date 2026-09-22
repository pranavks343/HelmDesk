"""c7: interrupt + resume. Mechanism: human_review pauses the graph via interrupt(); resuming
with Command(resume=...) continues execution from exactly that point."""

from langgraph.types import Command

from tests.conftest import thread_cfg

# u_alice has a real, over-the-auto-approve-limit duplicate invoice in data/crm.json, so her
# refund always requires human review (unlike the default `ctx` fixture's unknown test user,
# whose empty invoice list is auto-approved at $0).


def test_refund_pauses_at_human_review(graph, ctx_factory):
    ctx = ctx_factory(user_id="u_alice")
    cfg = thread_cfg("c07-pause")
    graph.invoke({"messages": [("human", "I was charged twice, please refund")]}, cfg, context=ctx)
    snap = graph.get_state(cfg)
    assert snap.next == ("human_review",)
    assert snap.tasks[0].interrupts
    assert snap.tasks[0].interrupts[0].value["type"] == "approve_refund"


def test_resume_with_approve_continues(graph, ctx_factory):
    ctx = ctx_factory(user_id="u_alice")
    cfg = thread_cfg("c07-resume")
    graph.invoke({"messages": [("human", "I was charged twice, please refund")]}, cfg, context=ctx)
    graph.invoke(Command(resume="approve"), cfg, context=ctx)
    # second interrupt (edit_reply) is now pending
    assert any(t.interrupts for t in graph.get_state(cfg).tasks)


def test_resume_with_reject_skips_execute_refund(graph, ctx_factory):
    ctx = ctx_factory(user_id="u_alice")
    cfg = thread_cfg("c07-reject")
    graph.invoke({"messages": [("human", "I was charged twice, please refund")]}, cfg, context=ctx)
    graph.invoke(Command(resume="reject"), cfg, context=ctx)
    result = graph.invoke(Command(resume=""), cfg, context=ctx)
    assert not result.get("refund_executed")
