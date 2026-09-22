"""Input guardrail: PII redaction, prompt-injection block, length cap (c26)."""

from __future__ import annotations

import re

from supportpilot.schemas import GuardrailVerdict

MAX_LEN = 4000
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
CARD_RE = re.compile(r"(?<![\w-])\d(?:[ -]?\d){12,18}(?![\w-])")
PHONE_RE = re.compile(r"(?<![\w-])(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?![\w-])")
INJECTION_RES = [
    re.compile(p, re.I)
    for p in (
        r"ignore (all |any )?(previous|prior|above) instructions",
        r"system prompt",
        r"you are now\b",
        r"disregard (your|the) (rules|instructions)",
    )
]


def luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
        alt = not alt
    return total % 10 == 0


def _card_sub(m: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", m.group())
    return "[CARD]" if 13 <= len(digits) <= 19 and luhn_ok(digits) else m.group()


def redact(text: str) -> tuple[str, list[str]]:
    flags: list[str] = []
    out = EMAIL_RE.sub("[EMAIL]", text)
    if out != text:
        flags.append("pii:email")
    after = CARD_RE.sub(_card_sub, out)
    if after != out:
        flags.append("pii:card")
    out, after = after, PHONE_RE.sub("[PHONE]", after)
    if after != out:
        flags.append("pii:phone")
    return after, flags


def screen(text: str) -> GuardrailVerdict:
    flags: list[str] = []
    allowed = True
    if len(text) > MAX_LEN:
        flags.append("too_long")
        allowed = False
    if any(p.search(text) for p in INJECTION_RES):
        flags.append("injection")
        allowed = False
    redacted, pii = redact(text)
    return GuardrailVerdict(allowed=allowed, flags=[*flags, *pii], redacted_text=redacted)
