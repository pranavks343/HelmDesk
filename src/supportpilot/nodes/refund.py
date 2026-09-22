"""execute_refund: idempotent, writes a JSON ledger (c19 replay safety)."""

from __future__ import annotations

import json
from pathlib import Path

from langgraph.config import get_config
from langgraph.runtime import Runtime

from supportpilot.config import ledger_path
from supportpilot.context import SupportContext
from supportpilot.state import ParentState


def _read_ledger(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        return {}


def _write_ledger(path: Path, ledger: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2, sort_keys=True))


def execute_refund(state: ParentState, runtime: Runtime[SupportContext]) -> dict:
    refund = state.get("refund")
    try:
        thread_id = get_config().get("configurable", {}).get("thread_id") or runtime.context.user_id
    except RuntimeError:
        thread_id = runtime.context.user_id

    if refund is None:
        return {"audit": ["execute_refund: no refund proposal, skipped"]}

    key = f"{thread_id}:{refund.invoice_id}"
    path = ledger_path()
    ledger = _read_ledger(path)

    if key in ledger:
        return {"refund_executed": True, "audit": [f"refund already executed ({key})"]}

    ledger[key] = {
        "invoice_id": refund.invoice_id,
        "amount": refund.amount,
        "currency": refund.currency,
        "reason": refund.reason,
    }
    _write_ledger(path, ledger)
    return {"refund_executed": True, "audit": [f"refund executed ({key})"]}
