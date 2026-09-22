"""c5: threads / state APIs. Mechanism: get_state and get_state_history expose the checkpointed
timeline of a thread; update_state lets you write into a past checkpoint."""

from tests.conftest import thread_cfg


def test_get_state_reflects_final_values(graph, ctx):
    cfg = thread_cfg("c05-state")
    graph.invoke({"messages": [("human", "how do I set up sso")]}, cfg, context=ctx)
    snap = graph.get_state(cfg)
    assert snap.values.get("final_answer")
    assert snap.next == ()


def test_get_state_history_has_multiple_checkpoints(graph, ctx):
    cfg = thread_cfg("c05-history")
    graph.invoke({"messages": [("human", "how do I set up sso")]}, cfg, context=ctx)
    hist = list(graph.get_state_history(cfg))
    assert len(hist) > 5
    # steps are ordered newest-first
    ids = [h.config["configurable"]["checkpoint_id"] for h in hist]
    assert len(set(ids)) == len(ids)


def test_update_state_writes_into_a_past_checkpoint(graph, ctx):
    cfg = thread_cfg("c05-update")
    graph.invoke({"messages": [("human", "how do I set up sso")]}, cfg, context=ctx)
    hist = list(graph.get_state_history(cfg))
    early = hist[-2]  # near the start
    new_cfg = graph.update_state(
        {"configurable": {**early.config["configurable"], "checkpoint_ns": ""}},
        {"audit": ["manually patched"]},
    )
    patched = graph.get_state(new_cfg)
    assert "manually patched" in patched.values.get("audit", [])
