"""c9: subgraph with a shared schema. Mechanism: kb_agent is compiled standalone against KBState
and also embedded directly as a parent node (`add_node("kb_agent", compiled_graph)`); the same
keys (citations, draft_answer, grade) flow through untouched."""

from supportpilot.context import SupportContext
from supportpilot.subgraphs.kb_agent import build_kb_graph
from tests.conftest import thread_cfg


def test_kb_agent_runs_standalone():
    kb = build_kb_graph()
    result = kb.invoke(
        {"query": "sso setup", "rewrite_count": 0},
        thread_cfg("c09-standalone"),
        context=SupportContext(user_id="u1"),
    )
    assert result["citations"]
    assert result["draft_answer"]
    assert result["grade"] is not None


def test_kb_agent_embedded_in_parent_shares_keys(graph, ctx):
    cfg = thread_cfg("c09-embedded")
    result = graph.invoke({"messages": [("human", "how do I set up sso")]}, cfg, context=ctx)
    assert result["citations"], "citations key flowed from subgraph into parent state directly"
    assert result["route"].next == "kb_agent"
