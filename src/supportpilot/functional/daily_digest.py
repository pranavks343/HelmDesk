"""Daily digest: a batch job with plain Python control flow, no need to visualise as a graph.
Uses the Functional API instead of StateGraph (c29).

Pick StateGraph when you need branching/looping control flow a human should be able to see
(the supervisor's routing, the KB grade/rewrite loop) or human-in-the-loop pauses mid-conversation.
Pick the Functional API for linear/batch/fan-out-then-join jobs like this one, where the logic is
just "map, then map, then maybe pause once" - a nightly digest, a data pipeline, a report
generator. `@task` results are individually checkpointed, so resuming after a crash or an
`interrupt()` does not redo already-completed tasks (tested in test_c29_functional).
"""

from __future__ import annotations

from typing import Any

from langgraph.func import entrypoint, task
from langgraph.runtime import Runtime
from langgraph.store.memory import InMemoryStore
from langgraph.types import interrupt

from supportpilot.context import SupportContext
from supportpilot.llm.factory import get_gateway
from supportpilot.memory.store import digest_namespace
from supportpilot.persistence import memory_checkpointer


@task
def summarize_ticket(ticket: dict, runtime: Runtime[SupportContext]) -> str:
    gateway = get_gateway(runtime.context)
    from langchain_core.messages import HumanMessage

    text = ticket.get("summary") or ticket.get("text", "")
    return gateway.summarize("", [HumanMessage(content=text)]) or text


@task
def classify_sentiment(summary: str) -> str:
    low = summary.lower()
    if any(w in low for w in ("refund", "angry", "broken", "down", "not working", "urgent")):
        return "negative"
    if any(w in low for w in ("thanks", "great", "resolved", "love")):
        return "positive"
    return "neutral"


def _digest_workflow(tickets: list[dict], *, previous: dict[str, Any] | None = None) -> Any:
    # `runtime` is injected by the @task decorator at call time (same mechanism as node functions
    # that declare a `runtime: Runtime[...]` parameter) - the type stub doesn't model that.
    futures = [summarize_ticket(t) for t in tickets]  # type: ignore[call-arg]  # parallel
    summaries = [f.result() for f in futures]
    sentiments = [classify_sentiment(s).result() for s in summaries]

    approved = interrupt({"type": "approve_digest", "preview": summaries[:3]})
    if not approved:
        return entrypoint.final(value={"sent": False}, save=previous)

    digest = {
        "ticket_count": len(tickets),
        "summaries": summaries,
        "sentiments": sentiments,
        "negative_count": sentiments.count("negative"),
    }
    return entrypoint.final(value={"sent": True, "digest": digest}, save=digest)


_digest_workflow.__name__ = "daily_digest"  # entrypoint() names the node after the function


# Standalone use (CLI `digest` command, tests): bring your own persistence, so interrupt/resume
# and @task memoization work without a running server.
daily_digest = entrypoint(
    checkpointer=memory_checkpointer(), store=InMemoryStore(), context_schema=SupportContext
)(_digest_workflow)


def make_daily_digest() -> Any:
    """For langgraph.json (Studio/platform, c30). Unlike `daily_digest` above, this must NOT bake
    in a checkpointer/store - `langgraph dev` (and the deployed platform) refuses to load a
    Functional-API entrypoint that already has its own persistence wired in, the same way
    `graph.make_graph()` omits them for the StateGraph (see docs/API_NOTES.md)."""
    return entrypoint(context_schema=SupportContext)(_digest_workflow)


def save_digest_to_store(store: Any, date: str, digest: dict[str, Any]) -> None:
    store.put(digest_namespace(date), "digest", digest)
