"""c31: pytest evaluation harness. Mechanism: golden.jsonl has >=30 labelled cases; run_eval.py
scores them and writes evals/report.md; test_eval_thresholds.py (tests/test_eval_thresholds.py)
fails the build if the fake-provider thresholds regress."""

import json
from pathlib import Path

GOLDEN = Path(__file__).resolve().parents[2] / "evals" / "golden.jsonl"


def test_golden_set_has_at_least_30_cases():
    lines = GOLDEN.read_text().strip().splitlines()
    assert len(lines) >= 30
    cases = [json.loads(line) for line in lines]
    ids = {c["id"] for c in cases}
    assert len(ids) == len(cases), "golden case ids must be unique"


def test_golden_cases_have_required_fields():
    cases = [json.loads(line) for line in GOLDEN.read_text().strip().splitlines()]
    required = {"id", "input", "user_id", "expected_route"}
    for c in cases:
        assert required.issubset(c.keys()), f"{c['id']} missing required fields"


def test_metrics_score_case_marks_route_mismatch():
    from evals.metrics import score_case

    golden = {"id": "x", "expected_route": "kb_agent"}
    outcome = {"route": "tech_agent", "blocked": False}
    result = score_case(golden, outcome)
    assert not result.passed
    assert not result.route_correct
