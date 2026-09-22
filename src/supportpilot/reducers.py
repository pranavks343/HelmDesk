"""Custom state reducers (c1). Pure functions: no mutation, tolerate empty/None inputs."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from supportpilot.schemas import Citation


def _as_citation(item: Citation | dict[str, Any]) -> Citation:
    return item if isinstance(item, Citation) else Citation.model_validate(item)


def merge_citations(
    left: Iterable[Citation] | None, right: Iterable[Citation] | None
) -> list[Citation]:
    """Union by ``doc_id``, keep the higher score, sort by score descending."""
    best: dict[str, Citation] = {}
    for raw in [*(left or []), *(right or [])]:
        cite = _as_citation(raw)
        current = best.get(cite.doc_id)
        if current is None or (cite.score, cite.snippet, cite.title) > (
            current.score,
            current.snippet,
            current.title,
        ):
            best[cite.doc_id] = cite
    return sorted(best.values(), key=lambda c: (-c.score, c.doc_id))


def append_unique(left: list[str] | None, right: list[str] | None) -> list[str]:
    """Append preserving order, skipping duplicates. Used for guardrail flags and the audit trail."""
    out: list[str] = []
    for item in [*(left or []), *(right or [])]:
        if item not in out:
            out.append(item)
    return out
