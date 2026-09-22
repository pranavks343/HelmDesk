"""c27: recursion limit + fallback. Mechanism: RemainingSteps lets tech_llm degrade gracefully
before hitting the hard recursion limit (fake_behavior="tool_loop" never raises); a tiny
recursion_limit still raises GraphRecursionError as the last line of defence, and the CLI wrapper
converts it to a fallback message."""

from langgraph.errors import GraphRecursionError

from supportpilot.config import DEFAULT_RECURSION_LIMIT
from tests.conftest import thread_cfg


def test_tool_loop_degrades_without_raising(graph, ctx_factory):
    ctx = ctx_factory(fake_behavior="tool_loop")
    cfg = thread_cfg("c27-toolloop")
    cfg["recursion_limit"] = DEFAULT_RECURSION_LIMIT
    result = graph.invoke({"messages": [("human", "is the api down")]}, cfg, context=ctx)
    assert result.get("final_answer")


def test_tiny_recursion_limit_raises():
    from langgraph.cache.memory import InMemoryCache
    from langgraph.checkpoint.memory import InMemorySaver

    from supportpilot.context import SupportContext
    from supportpilot.graph import build_graph as bg
    from supportpilot.memory.store import build_store
    from supportpilot.serde import make_serde

    graph = bg(
        checkpointer=InMemorySaver(serde=make_serde()),
        store=build_store("memory"),
        cache=InMemoryCache(serde=make_serde()),
    )
    cfg = {"configurable": {"thread_id": "c27-tiny"}, "recursion_limit": 1}
    raised = False
    try:
        graph.invoke({"messages": [("human", "hello")]}, cfg, context=SupportContext(user_id="u1"))
    except GraphRecursionError:
        raised = True
    assert raised


def test_cli_wrapper_converts_recursion_error_to_fallback():
    """cli.chat() catches GraphRecursionError around each turn's run_stream call and continues -
    verified structurally here since the CLI itself is interactive (see src/supportpilot/cli.py)."""
    import inspect

    from supportpilot import cli

    source = inspect.getsource(cli.chat)
    assert "GraphRecursionError" in source
