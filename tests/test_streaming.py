"""Direct coverage of streaming.py's render/driver helpers (c10, c22)."""

from __future__ import annotations

import asyncio

from rich.console import Console

from supportpilot.streaming import arun_stream, iter_stream, render_chunk, run_stream
from tests.conftest import thread_cfg


def test_render_chunk_handles_every_mode():
    console = Console(record=True)
    render_chunk(console, (), "updates", {"my_node": {"x": 1}})
    render_chunk(console, ("sub:1",), "custom", {"event": "hi"})
    render_chunk(console, (), "debug", {"step": 1, "type": "task"})
    render_chunk(console, (), "values", {"messages": []})
    from langchain_core.messages import AIMessageChunk

    render_chunk(console, (), "messages", (AIMessageChunk(content="hi"), {"langgraph_node": "generate"}))
    render_chunk(console, (), "updates", {"__interrupt__": [{"value": "x"}]})
    output = console.export_text()
    assert "my_node" in output
    assert "interrupt" in output


def test_run_stream_returns_final_values(graph, ctx):
    console = Console(record=True)
    values = run_stream(
        graph, {"messages": [("human", "how do I set up sso")]}, thread_cfg("stream-1"), ctx, console
    )
    assert values.get("final_answer")


def test_iter_stream_yields_raw_tuples(graph, ctx):
    chunks = list(
        iter_stream(graph, {"messages": [("human", "how do I set up sso")]}, thread_cfg("stream-2"), ctx)
    )
    assert chunks
    assert all(len(c) == 3 for c in chunks)


def test_arun_stream_returns_final_values(graph, ctx):
    console = Console(record=True)

    async def go():
        return await arun_stream(
            graph, {"messages": [("human", "how do I set up sso")]}, thread_cfg("stream-3"), ctx, console
        )

    values = asyncio.run(go())
    assert values.get("final_answer")
