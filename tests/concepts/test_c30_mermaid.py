"""c30: Studio + Mermaid export. Mechanism: langgraph.json declares both graphs for `langgraph
dev`; export_graph.py's draw_mermaid(xray=True) output names every parent node and every
subgraph-internal node."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PARENT_NODES = [
    "input_guardrail", "blocked_reply", "load_memory", "manage_context", "supervisor",
    "billing_agent", "fallback", "human_review", "execute_refund", "compose_reply",
    "output_guardrail", "save_memory",
]
SUBGRAPH_NODES = [
    "plan_retrieval", "retrieve_source", "rerank_forum", "merge_sources", "generate", "grade",
    "rewrite", "flag_low_confidence", "tech_llm", "tools", "load_account", "assess_refund",
]


def test_langgraph_json_declares_both_graphs():
    cfg = json.loads((ROOT / "langgraph.json").read_text())
    assert "supportpilot" in cfg["graphs"]
    assert "daily_digest" in cfg["graphs"]


def test_mermaid_export_contains_every_node():
    from scripts.export_graph import main

    mermaid = main(xray=True)
    for name in PARENT_NODES + SUBGRAPH_NODES:
        assert name in mermaid, f"{name} missing from mermaid export"


def test_make_graph_compiles_without_a_checkpointer_or_store():
    """`make_graph()` is what `langgraph dev` loads (langgraph.json); per the spec it must NOT
    supply its own checkpointer/store - the dev server injects those. It should compile cleanly
    and be invokable structurally, even though a bare `.invoke()` outside the dev server will
    hit nodes that need a store (proven separately, not here)."""
    from supportpilot.graph import make_graph

    graph = make_graph()
    assert graph.checkpointer is None
    assert graph.store is None
    node_names = set(graph.get_graph(xray=False).nodes.keys())
    assert "supervisor" in node_names and "billing_agent" in node_names
