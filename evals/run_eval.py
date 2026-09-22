"""Runs the golden set through the graph and writes evals/report.md (c31)."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evals.metrics import aggregate, score_case  # noqa: E402
from langchain_core.messages import HumanMessage, ToolMessage  # noqa: E402
from langgraph.cache.memory import InMemoryCache  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from supportpilot.context import SupportContext  # noqa: E402
from supportpilot.graph import build_graph  # noqa: E402
from supportpilot.llm.factory import get_gateway  # noqa: E402
from supportpilot.memory.store import build_store  # noqa: E402
from supportpilot.serde import make_serde  # noqa: E402
from supportpilot.subgraphs.kb_agent import reset_flaky_counters  # noqa: E402

GOLDEN = Path(__file__).parent / "golden.jsonl"
REPORT = Path(__file__).parent / "report.md"


def _run_case(graph: Any, case: dict[str, Any], provider: str) -> dict[str, Any]:
    thread_id = f"eval-{case['id']}-{uuid.uuid4().hex[:6]}"
    cfg = {"configurable": {"thread_id": thread_id}}
    ctx = SupportContext(user_id=case["user_id"], llm_provider=provider)  # type: ignore[arg-type]
    result = graph.invoke({"messages": [HumanMessage(content=case["input"])]}, cfg, context=ctx)

    snap = graph.get_state(cfg)
    interrupted = bool(snap.next)
    blocked = "input blocked" in result.get("audit", [])
    route = None if blocked else (result.get("route").next if result.get("route") else None)
    tools_called = [m.name for m in result.get("messages", []) if isinstance(m, ToolMessage) and m.name]
    citations = result.get("citations", [])
    citations_valid = True
    if route == "kb_agent" and result.get("final_answer"):
        cited_ids = {c.doc_id for c in citations}
        import re

        mentioned = set(re.findall(r"\[([a-z0-9][a-z0-9-]+)\]", result["final_answer"]))
        citations_valid = bool(mentioned) and mentioned.issubset(cited_ids)

    steps = len(list(graph.get_state_history(cfg)))
    return {
        "blocked": blocked,
        "route": route,
        "tools_called": tools_called,
        "citations": citations,
        "citations_valid": citations_valid,
        "interrupted": interrupted,
        "final_answer": result.get("final_answer", ""),
        "steps": steps,
    }


def main(provider: str = "fake") -> None:
    get_gateway.cache_clear()
    reset_flaky_counters()
    cases = [json.loads(line) for line in GOLDEN.read_text().strip().splitlines()]

    graph = build_graph(
        checkpointer=InMemorySaver(serde=make_serde()),
        store=build_store("memory"),
        cache=InMemoryCache(serde=make_serde()),
    )

    results = []
    rows = []
    for case in cases:
        outcome = _run_case(graph, case, provider)
        result = score_case(case, outcome)
        results.append(result)
        rows.append((case, outcome, result))

    agg = aggregate(results)

    lines = [
        f"# SupportPilot eval report ({provider})",
        "",
        f"**{agg['passed']}/{agg['total']} cases passed**",
        "",
        f"- route accuracy: {agg['route_accuracy']:.2%}",
        f"- tool precision/recall: {agg['tool_precision_recall']:.2%}",
        f"- citation validity rate: {agg['citation_validity_rate']:.2%}",
        f"- guardrail block precision: {agg['guardrail_block_precision']:.2%}",
        f"- interrupt correctness: {agg['interrupt_correctness']:.2%}",
        f"- mean steps per run: {agg['mean_steps']:.1f}",
        "",
        "| id | pass | route | notes |",
        "|---|---|---|---|",
    ]
    for case, outcome, result in rows:
        status = "✅" if result.passed else "❌"
        notes = "; ".join(result.notes) or "-"
        lines.append(f"| {case['id']} | {status} | {outcome['route']} | {notes} |")

    REPORT.write_text("\n".join(lines) + "\n")
    print(f"wrote {REPORT}: {agg['passed']}/{agg['total']} passed")
    print(agg)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="fake", choices=["fake", "anthropic"])
    args = parser.parse_args()
    main(provider=args.provider)
