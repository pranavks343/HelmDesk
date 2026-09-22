"""Agentic RAG subgraph: fan-out retrieval, cache, retry, deferred merge, grade -> rewrite loop.

Concepts: Send (c3), RetryPolicy (c8), Subgraphs (c9), Agentic RAG (c13), CachePolicy (c23),
defer=True (c24).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from langgraph.cache.memory import InMemoryCache
from langgraph.config import get_config, get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.types import CachePolicy, Command, RetryPolicy, Send

from supportpilot.config import KB_SOURCES, REWRITE_LIMIT
from supportpilot.context import SupportContext
from supportpilot.errors import TransientSourceError
from supportpilot.llm.factory import get_gateway
from supportpilot.retrieval.tfidf import normalize, search
from supportpilot.serde import make_serde
from supportpilot.state import KBState

# Keyed on (thread_id, query, source): counts remaining forced failures per (thread, query) so
# the flaky-forum demo (c8) is deterministic and resettable between tests.
_FORUM_FAILURES: Counter[tuple[str, str]] = Counter()


def reset_flaky_counters() -> None:
    """Test helper: clears the module-level flaky-forum counter."""
    _FORUM_FAILURES.clear()


def _thread_id() -> str:
    try:
        return str(get_config().get("configurable", {}).get("thread_id", "no-thread"))
    except RuntimeError:
        return "no-thread"


def plan_retrieval(state: KBState) -> dict:
    return {}


def fanout_sources(state: KBState) -> list[Send]:
    query = state.get("query", "")
    return [Send("retrieve_source", {"query": query, "source": s}) for s in KB_SOURCES]


def retrieve_source(payload: dict[str, Any], runtime: Runtime[SupportContext]) -> Command:
    query, source = payload["query"], payload["source"]
    writer = get_stream_writer()

    if source == "forum":
        key = (_thread_id(), normalize(query))
        remaining = _FORUM_FAILURES.get(key)
        if remaining is None:
            remaining = runtime.context.flaky_forum_failures
            _FORUM_FAILURES[key] = remaining
        if _FORUM_FAILURES[key] > 0:
            _FORUM_FAILURES[key] -= 1
            raise TransientSourceError(f"forum source flaked for {key}")

    hits = search(query, source, k=3)
    writer({"event": "retrieve", "source": source, "hits": len(hits)})

    goto = "rerank_forum" if source == "forum" else "merge_sources"
    return Command(update={"raw_hits": hits}, goto=goto)


def rerank_forum(state: KBState) -> dict:
    forum_hits = [c for c in state.get("raw_hits", []) if c.source == "forum"]
    writer = get_stream_writer()
    writer({"event": "rerank_forum", "count": len(forum_hits)})
    # Extra hop: forum content is noisier, so re-sort by score again (already sorted by search,
    # but this is where a real system would re-score with a cross-encoder).
    return {}


def merge_sources(state: KBState) -> dict:
    """defer=True (c24): runs exactly once, after every fan-out branch has finished - not once
    per uneven branch completion."""
    writer = get_stream_writer()
    top = sorted(state.get("raw_hits", []), key=lambda c: -c.score)[:5]
    writer({"event": "merge_sources", "citations": len(top)})
    return {"citations": top}


def generate(state: KBState, runtime: Runtime[SupportContext]) -> dict:
    gateway = get_gateway(runtime.context)
    ai = gateway.generate_answer(state.get("query", ""), state.get("citations", []))
    return {"draft_answer": str(ai.content)}


def grade(state: KBState, runtime: Runtime[SupportContext]) -> dict:
    gateway = get_gateway(runtime.context)
    result = gateway.grade(state.get("query", ""), state.get("draft_answer", ""), state.get("citations", []))
    return {"grade": result}


def route_after_grade(state: KBState) -> str:
    result = state.get("grade")
    if result is not None and result.relevant and result.grounded:
        return END
    if state.get("rewrite_count", 0) < REWRITE_LIMIT:
        return "rewrite"
    return "flag_low_confidence"


def rewrite(state: KBState, runtime: Runtime[SupportContext]) -> dict:
    gateway = get_gateway(runtime.context)
    result = state.get("grade")
    rewritten = gateway.rewrite(state.get("query", ""), result.missing if result else None)
    # raw_hits keeps accumulating (it's an `add` reducer - full retrieval history, useful for
    # debugging); citations dedupes via merge_citations so stale, lower-scored hits don't linger.
    return {"query": rewritten.query, "rewrite_count": state.get("rewrite_count", 0) + 1}


def flag_low_confidence(state: KBState) -> dict:
    return {"low_confidence": True}


def build_kb_graph() -> CompiledStateGraph[KBState, SupportContext, KBState, KBState]:
    g = StateGraph(KBState, context_schema=SupportContext)
    g.add_node("plan_retrieval", plan_retrieval)
    g.add_node(
        "retrieve_source",
        retrieve_source,  # type: ignore[arg-type]  # input is a Send payload, not full KBState
        destinations=("rerank_forum", "merge_sources"),
        retry_policy=RetryPolicy(max_attempts=3, initial_interval=0.05, retry_on=TransientSourceError),
        cache_policy=CachePolicy(
            # .get(...) with defaults: draw_graph(xray=True) probes every node's cache key with a
            # blank/example payload to enumerate possible tasks, not just real Send args.
            key_func=lambda payload: f"{payload.get('source', '?')}::{normalize(payload.get('query', ''))}",
            ttl=300,
        ),
    )
    g.add_node("rerank_forum", rerank_forum)
    g.add_node("merge_sources", merge_sources, defer=True)
    g.add_node("generate", generate)
    g.add_node("grade", grade)
    g.add_node("rewrite", rewrite)
    g.add_node("flag_low_confidence", flag_low_confidence)

    g.add_edge(START, "plan_retrieval")
    g.add_conditional_edges("plan_retrieval", fanout_sources, ["retrieve_source"])
    g.add_edge("rerank_forum", "merge_sources")
    g.add_edge("merge_sources", "generate")
    g.add_edge("generate", "grade")
    g.add_conditional_edges("grade", route_after_grade, ["rewrite", "flag_low_confidence", END])
    g.add_edge("rewrite", "plan_retrieval")
    g.add_edge("flag_low_confidence", END)
    return g.compile(cache=InMemoryCache(serde=make_serde()))
