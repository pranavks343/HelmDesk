"""c29: Functional API. Mechanism: @entrypoint/@task run a batch job (fan-out summarize, then
classify, then one interrupt) without StateGraph; @task results are individually checkpointed so
a resume doesn't redo already-completed tasks."""

from langgraph.types import Command

from supportpilot.context import SupportContext
from supportpilot.functional.daily_digest import daily_digest, summarize_ticket
from supportpilot.llm.factory import get_gateway


def test_digest_fans_out_and_pauses_for_approval():
    get_gateway.cache_clear()
    ctx = SupportContext(user_id="ops")
    cfg = {"configurable": {"thread_id": "c29-pause"}}
    tickets = [{"summary": "refund please, charged twice"}, {"summary": "thanks, all resolved"}]
    daily_digest.invoke(tickets, cfg, context=ctx)
    snap = daily_digest.get_state(cfg)
    assert snap.next == ("daily_digest",)
    assert snap.tasks[0].interrupts[0].value["type"] == "approve_digest"


def test_approve_sends_digest_reject_does_not():
    get_gateway.cache_clear()
    ctx = SupportContext(user_id="ops")
    tickets = [{"summary": "urgent broken login"}, {"summary": "great, thanks!"}]

    cfg1 = {"configurable": {"thread_id": "c29-approve"}}
    daily_digest.invoke(tickets, cfg1, context=ctx)
    r1 = daily_digest.invoke(Command(resume=True), cfg1, context=ctx)
    assert r1["sent"] is True
    assert r1["digest"]["ticket_count"] == 2
    assert r1["digest"]["negative_count"] >= 1

    cfg2 = {"configurable": {"thread_id": "c29-reject"}}
    daily_digest.invoke(tickets, cfg2, context=ctx)
    r2 = daily_digest.invoke(Command(resume=False), cfg2, context=ctx)
    assert r2 == {"sent": False}


def test_task_results_are_not_redone_on_resume():
    get_gateway.cache_clear()
    calls = {"n": 0}
    from supportpilot.functional import daily_digest as dd_mod

    original_func = summarize_ticket.func

    def counting(ticket, runtime):
        calls["n"] += 1
        return original_func(ticket, runtime)

    dd_mod.summarize_ticket.func = counting
    try:
        ctx = SupportContext(user_id="ops")
        cfg = {"configurable": {"thread_id": "c29-norepeat"}}
        tickets = [{"summary": "one issue"}, {"summary": "another issue"}]
        dd_mod.daily_digest.invoke(tickets, cfg, context=ctx)
        calls_before_resume = calls["n"]
        dd_mod.daily_digest.invoke(Command(resume=True), cfg, context=ctx)
        assert calls["n"] == calls_before_resume, "summarize_ticket was not re-run on resume"
    finally:
        dd_mod.summarize_ticket.func = original_func
