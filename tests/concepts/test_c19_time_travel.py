"""c19: replay + fork. Mechanism: replay re-executes from a past checkpoint (downstream nodes
re-run); fork writes new values into a past checkpoint and continues from there; execute_refund's
idempotency key means neither replay nor a duplicate resume double-refunds."""

import json

from supportpilot.persistence import fork, list_history, replay
from tests.conftest import thread_cfg


def test_replay_reruns_downstream_nodes(graph, ctx):
    cfg = thread_cfg("c19-replay")
    graph.invoke({"messages": [("human", "how do I set up sso")]}, cfg, context=ctx)
    hist = list_history(graph, "c19-replay")
    mid = hist[len(hist) // 2]
    replayed = replay(graph, "c19-replay", mid["checkpoint_id"], context=ctx)
    assert replayed.get("final_answer")


def test_fork_creates_a_new_branch_without_touching_the_original(graph, ctx_factory, tmp_path, monkeypatch):
    ctx = ctx_factory(user_id="u_alice", refund_auto_approve_limit=20.0)
    cfg = thread_cfg("c19-fork")
    graph.invoke({"messages": [("human", "I was charged twice, please refund")]}, cfg, context=ctx)
    original_next = graph.get_state(cfg).next
    assert original_next == ("human_review",)

    hist = list_history(graph, "c19-fork")
    before_hr = next(h for h in hist if h["next"] == ("human_review",))
    ckpt_id = before_hr["checkpoint_id"]
    snap_cfg = {"configurable": {"thread_id": "c19-fork", "checkpoint_ns": "", "checkpoint_id": ckpt_id}}
    refund = graph.get_state(snap_cfg).values["refund"]
    small_refund = refund.model_copy(update={"amount": 5.0, "auto_approvable": True})

    result = fork(graph, "c19-fork", ckpt_id, {"refund": small_refund}, as_node="billing_agent", context=ctx)
    assert result.get("refund_executed"), "forked branch auto-approved, no interrupt"

    # original branch (interrupted) is still present in history
    hist_after = list_history(graph, "c19-fork")
    assert any(h["next"] == ("human_review",) for h in hist_after)


def test_replay_does_not_double_refund(graph, ctx_factory, monkeypatch, tmp_path):
    ledger = tmp_path / "ledger.json"
    monkeypatch.setenv("SUPPORTPILOT_LEDGER", str(ledger))
    ctx = ctx_factory(user_id="u_bob")  # small refund, auto-approved
    cfg = thread_cfg("c19-noduplicate")
    graph.invoke({"messages": [("human", "I think I was billed twice")]}, cfg, context=ctx)
    first_ledger = json.loads(ledger.read_text())
    assert len(first_ledger) == 1

    hist = list_history(graph, "c19-noduplicate")
    # replay from an early checkpoint - execute_refund will re-run but must be a no-op
    early = hist[-2]
    replay(graph, "c19-noduplicate", early["checkpoint_id"], context=ctx)
    second_ledger = json.loads(ledger.read_text())
    assert second_ledger == first_ledger, "no duplicate refund entry after replay"
