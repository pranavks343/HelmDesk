"""Renderers for every stream mode, used by the CLI (c10, c22)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from langchain_core.messages import AIMessageChunk
from rich.console import Console

TOKEN_NODES = {"generate", "compose_reply"}


def _ns_label(namespace: tuple[str, ...]) -> str:
    return "/".join(p.split(":")[0] for p in namespace) if namespace else "parent"


def render_chunk(console: Console, namespace: tuple[str, ...], mode: str, chunk: Any) -> None:
    ns = _ns_label(namespace)
    if mode == "updates":
        if not isinstance(chunk, dict):
            return
        for node, update in chunk.items():
            if node == "__interrupt__":
                console.print(f"[bold yellow]⏸  interrupt[/] ({ns}): {update}")
                continue
            keys = sorted(update.keys()) if isinstance(update, dict) else []
            console.print(f"[cyan]→ {node}[/] ({ns}) updated: {keys}")
    elif mode == "custom":
        console.print(f"[dim]· {ns}: {chunk}[/]")
    elif mode == "debug":
        step = chunk.get("step") if isinstance(chunk, dict) else None
        payload_type = chunk.get("type") if isinstance(chunk, dict) else None
        console.print(f"[magenta]debug[/] ({ns}) step={step} type={payload_type}")
    elif mode == "messages":
        msg, metadata = chunk
        node = metadata.get("langgraph_node") if isinstance(metadata, dict) else None
        if node not in TOKEN_NODES:
            return
        if isinstance(msg, AIMessageChunk) and msg.content:
            console.print(str(msg.content), end="", style="green")
    elif mode == "values":
        keys = sorted(chunk.keys()) if isinstance(chunk, dict) else []
        console.print(f"[blue]values[/] ({ns}): {keys}")


def run_stream(
    graph: Any,
    inputs: Any,
    config: dict,
    context: Any,
    console: Console,
    modes: list[str] | None = None,
) -> dict:
    """Sync streaming driver. Returns the final state values."""
    modes = modes or ["updates", "custom", "messages"]
    for namespace, mode, chunk in graph.stream(
        inputs, config, context=context, stream_mode=modes, subgraphs=True
    ):
        render_chunk(console, namespace, mode, chunk)
    console.print()
    return graph.get_state(config).values


async def arun_stream(
    graph: Any,
    inputs: Any,
    config: dict,
    context: Any,
    console: Console,
    modes: list[str] | None = None,
) -> dict:
    """Async streaming driver (uses AsyncSqliteSaver-backed graphs)."""
    modes = modes or ["updates", "custom", "messages"]
    async for namespace, mode, chunk in graph.astream(
        inputs, config, context=context, stream_mode=modes, subgraphs=True
    ):
        render_chunk(console, namespace, mode, chunk)
    console.print()
    state = await graph.aget_state(config)
    return state.values


def iter_stream(
    graph: Any, inputs: Any, config: dict, context: Any, modes: list[str] | None = None
) -> Iterator[tuple]:
    """Non-rendering variant for tests: yields raw (namespace, mode, chunk) tuples."""
    modes = modes or ["updates", "custom", "messages"]
    yield from graph.stream(inputs, config, context=context, stream_mode=modes, subgraphs=True)
