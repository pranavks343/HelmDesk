"""Fails the build if the fake-provider eval harness regresses below agreed thresholds (c31)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import json  # noqa: E402

from evals.metrics import aggregate, score_case  # noqa: E402
from evals.run_eval import GOLDEN, _run_case  # noqa: E402
from langgraph.cache.memory import InMemoryCache  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from supportpilot.graph import build_graph  # noqa: E402
from supportpilot.memory.store import build_store  # noqa: E402
from supportpilot.serde import make_serde  # noqa: E402


def test_fake_provider_thresholds():
    cases = [json.loads(line) for line in GOLDEN.read_text().strip().splitlines()]
    graph = build_graph(
        checkpointer=InMemorySaver(serde=make_serde()),
        store=build_store("memory"),
        cache=InMemoryCache(serde=make_serde()),
    )
    results = [score_case(case, _run_case(graph, case, "fake")) for case in cases]
    agg = aggregate(results)

    assert agg["route_accuracy"] >= 0.95, agg
    assert agg["tool_precision_recall"] >= 0.95, agg
    assert agg["citation_validity_rate"] >= 1.0, agg
    blocked_cases = [r for r in results if not r.blocked_ok]
    assert not blocked_cases, f"guardrail-blocked-case leak: {[r.case_id for r in blocked_cases]}"
