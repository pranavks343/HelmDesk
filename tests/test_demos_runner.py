"""Runs the scripted demo suite (src/supportpilot/demos.py) inside pytest too - both for
coverage and as a regression net independent of the `supportpilot demo` CLI."""

from __future__ import annotations

from supportpilot import demos


def test_all_31_concept_demos_pass():
    results = demos.run_all()
    assert len(results) == 31
    failures = [(cid, detail) for cid, ok, detail in results if not ok]
    assert not failures, f"demo failures: {failures}"


def test_unknown_demo_id_reports_failure_not_crash():
    ok, detail = demos.run_one("c99")
    assert not ok
    assert "unknown concept id" in detail
