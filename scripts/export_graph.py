"""Writes the parent graph's Mermaid diagram (with subgraph internals) to docs/graph.mmd (c30)."""

from __future__ import annotations

from pathlib import Path

from supportpilot.graph import build_graph

OUT = Path(__file__).resolve().parents[1] / "docs" / "graph.mmd"


def main(xray: bool = True) -> str:
    graph = build_graph()
    mermaid = graph.get_graph(xray=xray).draw_mermaid()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(mermaid)
    print(f"wrote {OUT} ({len(mermaid)} chars)")
    return mermaid


if __name__ == "__main__":
    import sys

    main(xray="--no-xray" not in sys.argv)
