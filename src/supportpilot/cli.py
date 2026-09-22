"""Typer CLI (§14)."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated

import typer
from langgraph.cache.memory import InMemoryCache
from langgraph.errors import GraphRecursionError
from langgraph.types import Command
from rich.console import Console
from rich.table import Table

from supportpilot.config import DEFAULT_RECURSION_LIMIT
from supportpilot.context import SupportContext
from supportpilot.graph import build_graph
from supportpilot.memory.store import build_store, facts_namespace, profile_namespace
from supportpilot.persistence import (
    async_sqlite_checkpointer,
    list_history,
    show_state,
    sqlite_checkpointer,
)
from supportpilot.persistence import (
    fork as fork_thread,
)
from supportpilot.persistence import (
    replay as replay_thread,
)
from supportpilot.serde import make_serde
from supportpilot.streaming import arun_stream, run_stream

app = typer.Typer(help="SupportPilot: a LangGraph multi-agent customer-support desk demo.")
console = Console()

_STORE = None


def _shared_store():
    global _STORE
    if _STORE is None:
        _STORE = build_store("memory")
    return _STORE


def _compiled(checkpointer):
    return build_graph(
        checkpointer=checkpointer, store=_shared_store(), cache=InMemoryCache(serde=make_serde())
    )


def _graph_and_ctx(user: str, provider: str, use_async: bool = False):
    ctx = SupportContext(user_id=user, llm_provider=provider)  # type: ignore[arg-type]
    return _compiled(sqlite_checkpointer()), ctx


@app.command()
def chat(
    user: Annotated[str, typer.Option(help="Customer user id")],
    thread: Annotated[str, typer.Option(help="Thread id")],
    provider: Annotated[str, typer.Option(help="fake|anthropic")] = "fake",
    use_async: Annotated[bool, typer.Option("--async", help="Use the async streaming path")] = False,
    mode: Annotated[str, typer.Option(help="Comma-separated stream modes")] = "updates,custom,messages",
) -> None:
    """Start (or continue) a chat thread."""
    modes = mode.split(",")
    cfg = {"configurable": {"thread_id": thread}, "recursion_limit": DEFAULT_RECURSION_LIMIT}
    ctx = SupportContext(user_id=user, llm_provider=provider)  # type: ignore[arg-type]

    checkpointer = asyncio.run(async_sqlite_checkpointer()) if use_async else sqlite_checkpointer()
    graph = _compiled(checkpointer)

    console.print(f"[bold]SupportPilot[/] - user={user} thread={thread} provider={provider}. Ctrl+C to quit.")
    console.print()
    while True:
        text = typer.prompt("you")
        if text.strip().lower() in {"quit", "exit"}:
            break
        inputs = {"messages": [("human", text)]}
        try:
            if use_async:
                values = asyncio.run(arun_stream(graph, inputs, cfg, ctx, console, modes))
            else:
                values = run_stream(graph, inputs, cfg, ctx, console, modes)
        except GraphRecursionError:
            console.print("[red]Recursion limit hit - falling back to a safe reply.[/]")
            continue

        state = graph.get_state(cfg)
        if _pending_interrupts(state):
            _handle_interrupts(graph, cfg, ctx, state, use_async)
        else:
            console.print(f"[bold green]assistant:[/] {values.get('final_answer', '')}\n")


def _pending_interrupts(state) -> bool:
    # `.next` can read back as `()` on a *second* interrupt within the same re-entrant node call
    # (see docs/API_NOTES.md) - `.tasks[*].interrupts` is the authoritative check.
    return any(t.interrupts for t in state.tasks)


def _handle_interrupts(graph, cfg, ctx, state, use_async: bool) -> None:
    while _pending_interrupts(state):
        for task in state.tasks:
            for i in task.interrupts:
                console.print(f"[yellow]interrupt[/]: {i.value}")
                resume_raw = typer.prompt("resume value (approve/reject, or text)")
                resume_val: object = resume_raw
                if resume_raw.lower() in {"approve", "reject"}:
                    resume_val = resume_raw.lower()
                if use_async:
                    asyncio.run(arun_stream(graph, Command(resume=resume_val), cfg, ctx, console))
                else:
                    run_stream(graph, Command(resume=resume_val), cfg, ctx, console)
        state = graph.get_state(cfg)
    values = state.values
    console.print(f"[bold green]assistant:[/] {values.get('final_answer', '')}\n")


@app.command()
def resume(
    thread: Annotated[str, typer.Option()],
    user: Annotated[str, typer.Option()] = "unknown",
    provider: Annotated[str, typer.Option()] = "fake",
) -> None:
    """Continue a thread after a crash or interrupt without sending new input."""
    graph, ctx = _graph_and_ctx(user, provider)
    cfg = {"configurable": {"thread_id": thread}}
    values = run_stream(graph, None, cfg, ctx, console)
    console.print(f"[bold green]assistant:[/] {values.get('final_answer', '')}")


@app.command()
def state(thread: Annotated[str, typer.Option()], user: Annotated[str, typer.Option()] = "unknown") -> None:
    graph, _ = _graph_and_ctx(user, "fake")
    snap = show_state(graph, thread)
    console.print_json(data=_jsonable(snap))


@app.command()
def history(thread: Annotated[str, typer.Option()], user: Annotated[str, typer.Option()] = "unknown") -> None:
    graph, _ = _graph_and_ctx(user, "fake")
    rows = list_history(graph, thread)
    table = Table(title=f"history for {thread}")
    table.add_column("step")
    table.add_column("checkpoint_id")
    table.add_column("next")
    table.add_column("keys")
    for r in rows:
        table.add_row(str(r["step"]), r["checkpoint_id"][:8], str(r["next"]), ",".join(r["keys"][:6]))
    console.print(table)


@app.command()
def replay(
    thread: Annotated[str, typer.Option()],
    checkpoint: Annotated[str, typer.Option()],
    user: Annotated[str, typer.Option()] = "unknown",
) -> None:
    graph, ctx = _graph_and_ctx(user, "fake")
    result = replay_thread(graph, thread, checkpoint, context=ctx)
    console.print_json(data=_jsonable(result))


@app.command("fork")
def fork_cmd(
    thread: Annotated[str, typer.Option()],
    checkpoint: Annotated[str, typer.Option()],
    set_: Annotated[str, typer.Option("--set", help="dotted.path=value, e.g. refund.amount=5")],
    as_node: Annotated[str | None, typer.Option("--as-node")] = None,
    user: Annotated[str, typer.Option()] = "unknown",
) -> None:
    graph, ctx = _graph_and_ctx(user, "fake")
    path, _, raw_value = set_.partition("=")
    keys = path.split(".")
    try:
        value: object = json.loads(raw_value)
    except json.JSONDecodeError:
        value = raw_value

    snap_cfg = {"configurable": {"thread_id": thread, "checkpoint_ns": "", "checkpoint_id": checkpoint}}
    snap = graph.get_state(snap_cfg)
    current = snap.values.get(keys[0])
    if len(keys) > 1 and current is not None and hasattr(current, "model_copy"):
        current = current.model_copy(update={keys[1]: value})
        values = {keys[0]: current}
    else:
        values = {keys[0]: value}

    result = fork_thread(graph, thread, checkpoint, values, as_node=as_node, context=ctx)
    console.print_json(data=_jsonable(result))


@app.command()
def memory(
    user: Annotated[str, typer.Option()],
    search: Annotated[str | None, typer.Option()] = None,
) -> None:
    store = _shared_store()
    profile_item = store.get(profile_namespace(user), "profile")
    console.print("[bold]profile:[/]", profile_item.value if profile_item else {})
    if search:
        hits = store.search(facts_namespace(user), query=search, limit=5)
        for h in hits:
            console.print(f"  {h.score:.3f}  {h.value}")
    else:
        items = store.search(facts_namespace(user), query="", limit=20)
        for it in items:
            console.print(f"  {it.value}")


@app.command()
def digest(date: Annotated[str, typer.Option()]) -> None:
    from supportpilot.functional.daily_digest import daily_digest as dd

    cfg = {"configurable": {"thread_id": f"digest-{date}"}}
    tickets: list[dict] = []  # a real deployment would pull today's closed tickets
    ctx = SupportContext(user_id="ops")
    dd.invoke(tickets, cfg, context=ctx)  # type: ignore[call-overload]
    result = dd.invoke(Command(resume=True), cfg, context=ctx)  # type: ignore[call-overload]
    console.print_json(data=result)


@app.command("export-graph")
def export_graph_cmd(xray: Annotated[bool, typer.Option()] = True) -> None:
    from scripts.export_graph import main as export_main

    export_main(xray=xray)


@app.command()
def demo(name: Annotated[str, typer.Argument(help="c01..c31 or 'all'")]) -> None:
    from supportpilot import demos

    if name == "all":
        results = demos.run_all()
        table = Table(title="SupportPilot concept demos")
        table.add_column("concept")
        table.add_column("status")
        table.add_column("detail")
        passed = 0
        for cid, ok, detail in results:
            table.add_row(cid, "[green]PASS[/]" if ok else "[red]FAIL[/]", detail)
            passed += int(ok)
        console.print(table)
        console.print(f"\n{passed}/{len(results)} passed")
        if passed < len(results):
            raise typer.Exit(code=1)
    else:
        ok, detail = demos.run_one(name)
        console.print(f"{name}: {'PASS' if ok else 'FAIL'} - {detail}")
        if not ok:
            raise typer.Exit(code=1)


def _jsonable(obj: object) -> object:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


if __name__ == "__main__":
    app()
