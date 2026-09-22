"""c10: streaming modes, sync + async. Mechanism: graph.stream(..., stream_mode=[...],
subgraphs=True) yields (namespace, mode, chunk) tuples for every requested mode; astream mirrors
it for the async path."""

import pytest

from tests.conftest import thread_cfg


def test_all_five_stream_modes_emit(graph, ctx):
    cfg = thread_cfg("c10-modes")
    seen = set()
    for ns, mode, _chunk in graph.stream(
        {"messages": [("human", "how do I set up sso")]},
        cfg,
        context=ctx,
        stream_mode=["values", "updates", "debug", "custom", "messages"],
        subgraphs=True,
    ):
        seen.add(mode)
        assert isinstance(ns, tuple)
    assert seen == {"values", "updates", "debug", "custom", "messages"}


def test_subgraph_events_carry_a_nonempty_namespace(graph, ctx):
    cfg = thread_cfg("c10-ns")
    namespaces = set()
    # a single (non-list) stream_mode yields (namespace, chunk) pairs, not (namespace, mode, chunk)
    for ns, _chunk in graph.stream(
        {"messages": [("human", "how do I set up sso")]},
        cfg,
        context=ctx,
        stream_mode="updates",
        subgraphs=True,
    ):
        namespaces.add(ns)
    assert any(ns for ns in namespaces if ns), "at least one event came from inside kb_agent"


@pytest.mark.asyncio
async def test_async_stream_path(graph, ctx):
    cfg = thread_cfg("c10-async")
    modes = set()
    async for _ns, mode, _chunk in graph.astream(
        {"messages": [("human", "how do I set up sso")]},
        cfg,
        context=ctx,
        stream_mode=["updates", "messages"],
        subgraphs=True,
    ):
        modes.add(mode)
    assert modes == {"updates", "messages"}
