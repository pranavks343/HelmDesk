"""Output guardrail: grounding, PII leaks, refund-amount consistency, uncertainty (c26)."""

from __future__ import annotations

import re

from supportpilot.guardrails.input import CARD_RE, EMAIL_RE, PHONE_RE, luhn_ok
from supportpilot.schemas import Citation, RefundProposal

CITE_RE = re.compile(r"\[([a-z0-9][a-z0-9-]+)\]")
AMOUNT_RE = re.compile(r"(?:\$|USD|EUR|INR|€|₹)\s?(\d+(?:,\d{3})*(?:\.\d{1,2})?)")
UNCERTAINTY = ("not fully certain", "not certain", "may not be", "might not", "i'm not sure")
SAFE_TEXT = (
    "I'm sorry - I couldn't produce a reliable answer. I've flagged this ticket for a human "
    "specialist who will follow up shortly."
)


def has_pii(text: str) -> bool:
    if EMAIL_RE.search(text) or PHONE_RE.search(text):
        return True
    return any(luhn_ok(re.sub(r"\D", "", m.group())) for m in CARD_RE.finditer(text))


def check_output(
    text: str,
    *,
    route: str | None,
    citations: list[Citation],
    refund: RefundProposal | None,
    low_confidence: bool,
) -> list[str]:
    """Return a list of failure reasons (empty = pass)."""
    fails: list[str] = []
    if has_pii(text):
        fails.append("pii_leak")
    if route == "kb_agent":
        cited = CITE_RE.findall(text)
        known = {c.doc_id for c in citations}
        if not cited:
            fails.append("no_citation")
        elif any(c not in known for c in cited):
            fails.append("unknown_citation")
    if refund is not None:
        for m in AMOUNT_RE.finditer(text):
            if abs(float(m.group(1).replace(",", "")) - refund.amount) > 0.005:
                fails.append("refund_amount_mismatch")
                break
    if low_confidence and not any(p in text.lower() for p in UNCERTAINTY):
        fails.append("missing_uncertainty")
    return fails
