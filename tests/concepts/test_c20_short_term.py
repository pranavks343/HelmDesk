"""c20: trim + rolling summary. Mechanism: manage_context deletes old messages via RemoveMessage
once the thread is long, folding them into `summary`; llm_view separately trims the model's view
without touching state, and keeps tool_call/tool_result pairs intact."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from supportpilot.memory.short_term import keep_tail_boundary, llm_view
from tests.conftest import thread_cfg


def test_manage_context_summarizes_and_trims(graph, ctx_factory):
    ctx = ctx_factory(summarize_after_messages=4)
    cfg = thread_cfg("c20-trim")
    for i in range(6):
        graph.invoke({"messages": [("human", f"question {i} about backups")]}, cfg, context=ctx)
    final = graph.get_state(cfg).values
    assert final.get("summary")
    assert len(final["messages"]) < 12


def test_llm_view_does_not_mutate_state():
    messages = [HumanMessage(content=f"msg {i}") for i in range(20)]
    view = llm_view(messages, "a summary", ["fact one"], max_tokens=50)
    assert len(view) <= len(messages) + 1  # trimmed view + optional system header
    assert len(messages) == 20, "original list untouched"


def test_llm_view_prepends_summary_and_facts():
    view = llm_view([HumanMessage(content="hi")], "prior summary", ["likes email"])
    assert "prior summary" in view[0].content
    assert "likes email" in view[0].content


def test_keep_tail_boundary_never_splits_tool_call_pairs():
    messages = [
        HumanMessage(content="q", id="1"),
        AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "c1"}], id="2"),
        ToolMessage(content="r", tool_call_id="c1", id="3"),
        AIMessage(content="final", id="4"),
    ]
    # keep_last=2 would naively cut at index 2 (the ToolMessage), splitting it from the
    # AIMessage(tool_calls) at index 1 that produced it - the boundary must walk back past it.
    cut = keep_tail_boundary(messages, keep_last=2)
    assert cut <= 1, "boundary walked back past the tool_call/tool_result pair"
    kept_types = {type(m) for m in messages[cut:]}
    if ToolMessage in kept_types:
        assert any(getattr(m, "tool_calls", None) for m in messages[cut:] if isinstance(m, AIMessage))
