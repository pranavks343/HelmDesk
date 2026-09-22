"""c12: workflow vs agent routing. Mechanism: the KB pipeline is a fixed workflow (plan -> fanout
-> merge -> generate -> grade, same order every time); the supervisor is agentic (LLM judgement),
falling back to a deterministic rule router when confidence is low."""

from tests.conftest import thread_cfg


def test_low_confidence_llm_route_falls_back_to_rule_router(graph, ctx):
    cfg = thread_cfg("c12-fallback")
    result = graph.invoke({"messages": [("human", "asdkjaslkdj")]}, cfg, context=ctx)
    assert result["route"].next == "fallback"
    assert result["route"].reason.startswith("rule:") or result["route"].reason.startswith("fallback")


def test_clear_question_uses_llm_judgement(graph, ctx):
    cfg = thread_cfg("c12-agent")
    result = graph.invoke({"messages": [("human", "how do I configure webhooks")]}, cfg, context=ctx)
    assert result["route"].next == "kb_agent"
    assert result["route"].confidence >= 0.5


def test_kb_pipeline_runs_the_same_fixed_stage_order_every_time():
    from supportpilot.context import SupportContext
    from supportpilot.subgraphs.kb_agent import build_kb_graph

    kb = build_kb_graph()
    events = []
    for chunk in kb.stream(
        {"query": "sso setup", "rewrite_count": 0},
        thread_cfg("c12-pipeline"),
        context=SupportContext(user_id="u1"),
        stream_mode="updates",
    ):
        events.extend(chunk.keys())
    # merge_sources always follows retrieval, generate always follows merge, grade always follows generate
    assert events.index("merge_sources") < events.index("generate") < events.index("grade")
