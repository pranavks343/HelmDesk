"""Scoring functions for the evaluation harness (c31)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CaseResult:
    case_id: str
    passed: bool
    route_correct: bool
    tools_ok: bool
    citations_ok: bool
    interrupt_ok: bool
    blocked_ok: bool
    content_ok: bool
    steps: int
    notes: list[str] = field(default_factory=list)


def score_case(golden: dict[str, Any], outcome: dict[str, Any]) -> CaseResult:
    notes: list[str] = []

    blocked_ok = True
    if golden.get("expect_blocked"):
        blocked_ok = outcome.get("blocked", False)
        if not blocked_ok:
            notes.append("expected the input to be blocked, it wasn't")
    elif outcome.get("blocked"):
        blocked_ok = False
        notes.append("input was blocked but wasn't expected to be")

    route_correct = True
    if not golden.get("expect_blocked"):
        route_correct = outcome.get("route") == golden.get("expected_route")
        if not route_correct:
            notes.append(f"route: expected {golden.get('expected_route')}, got {outcome.get('route')}")

    expected_tools = set(golden.get("expected_tools", []))
    tools_ok = True
    if expected_tools:
        tools_ok = expected_tools.issubset(set(outcome.get("tools_called", [])))
        if not tools_ok:
            notes.append(f"tools: expected {expected_tools}, got {outcome.get('tools_called')}")

    citations_ok = True
    if golden.get("must_cite"):
        citations_ok = bool(outcome.get("citations")) and outcome.get("citations_valid", False)
        if not citations_ok:
            notes.append("expected valid citations, found none or invalid")

    interrupt_ok = True
    if "expect_interrupt" in golden:
        interrupt_ok = outcome.get("interrupted", False) == golden["expect_interrupt"]
        if not interrupt_ok:
            notes.append(
                f"interrupt: expected {golden['expect_interrupt']}, got {outcome.get('interrupted')}"
            )

    text = (outcome.get("final_answer") or "").lower()
    content_ok = True
    for must in golden.get("must_contain", []):
        if must.lower() not in text:
            content_ok = False
            notes.append(f"missing required text: {must!r}")
    for must_not in golden.get("must_not_contain", []):
        if must_not.lower() in text:
            content_ok = False
            notes.append(f"contains forbidden text: {must_not!r}")

    passed = all([blocked_ok, route_correct, tools_ok, citations_ok, interrupt_ok, content_ok])
    return CaseResult(
        case_id=golden["id"],
        passed=passed,
        route_correct=route_correct,
        tools_ok=tools_ok,
        citations_ok=citations_ok,
        interrupt_ok=interrupt_ok,
        blocked_ok=blocked_ok,
        content_ok=content_ok,
        steps=outcome.get("steps", 0),
        notes=notes,
    )


def aggregate(results: list[CaseResult]) -> dict[str, Any]:
    n = len(results) or 1
    return {
        "total": len(results),
        "passed": sum(r.passed for r in results),
        "route_accuracy": sum(r.route_correct for r in results) / n,
        "tool_precision_recall": sum(r.tools_ok for r in results) / n,
        "citation_validity_rate": sum(r.citations_ok for r in results) / n,
        "guardrail_block_precision": sum(r.blocked_ok for r in results) / n,
        "interrupt_correctness": sum(r.interrupt_ok for r in results) / n,
        "mean_steps": sum(r.steps for r in results) / n,
    }
