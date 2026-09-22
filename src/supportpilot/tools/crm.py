"""CRM-backed tools. ``lookup_invoice`` is called directly by the billing subgraph, not via ToolNode."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from supportpilot.config import CRM_PATH


def load_crm() -> dict[str, Any]:
    return json.loads(CRM_PATH.read_text())  # type: ignore[no-any-return]


@tool
def check_service_status(service: str) -> dict[str, Any]:
    """Return the current status of a Nimbus service (api, dashboard, sso, backups)."""
    svc = load_crm()["services"].get(service.lower())
    if svc is None:
        return {"service": service, "error": "unknown service"}
    return {"service": service.lower(), **svc}


@tool
def lookup_order(order_id: str) -> dict[str, Any]:
    """Look up an order (plan, seats, status) by id such as ORD-5001."""
    order = load_crm()["orders"].get(order_id.upper())
    if order is None:
        return {"order_id": order_id, "error": "order not found"}
    return {"order_id": order_id.upper(), **order}


@tool
def lookup_invoice(invoice_id: str) -> dict[str, Any]:
    """Look up an invoice (amount, date, status) by id such as INV-1001."""
    inv = load_crm()["invoices"].get(invoice_id.upper())
    if inv is None:
        return {"invoice_id": invoice_id, "error": "invoice not found"}
    return {"invoice_id": invoice_id.upper(), **inv}
