"""Swappable LLM gateway: FakeLLM (default, deterministic, offline) vs AnthropicLLM (opt-in).

Kept behind one small `Protocol` so `graph.py`'s nodes never know which is running - the same
"deterministic by default, real model opt-in" pattern used for the eval/test suite: CI and local
dev run entirely offline against FakeLLM, and swapping in a real model is one env var
(`LLM_PROVIDER=anthropic`), not a code change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from tools import KBHit, priority_score, sentiment

CATEGORIES = ("billing", "technical", "account", "general")
CATEGORY_KEYWORDS = {
    "billing": ("refund", "charge", "invoice", "billing", "payment", "subscription"),
    "technical": ("error", "bug", "crash", "down", "outage", "not working", "api", "sso", "login"),
    "account": ("password", "account", "access", "locked", "permission", "role"),
}


@dataclass(frozen=True)
class ClassifyResult:
    category: str
    priority: str
    confidence: float


@dataclass(frozen=True)
class DraftResult:
    text: str
    confidence: float


class LLMGateway(Protocol):
    def classify(self, title: str, context: list[str]) -> ClassifyResult: ...

    def draft_reply(self, title: str, context: list[str], kb_hits: list[KBHit]) -> DraftResult: ...


class FakeLLM:
    """Rule-based, deterministic. Never calls out to the network."""

    def classify(self, title: str, context: list[str]) -> ClassifyResult:
        text = " ".join([title, *context]).lower()
        category = "general"
        best_hits = 0
        for cat, keywords in CATEGORY_KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw in text)
            if hits > best_hits:
                best_hits = hits
                category = cat
        sentiment_label = sentiment(text)
        priority = priority_score(title, sentiment_label)
        # confidence scales with how unambiguous the keyword match was. A zero-hit ticket (no
        # category keyword at all) deliberately lands *below* graph.py's LOW_CONFIDENCE_SKIP_DRAFT
        # threshold - if we can't even guess a category, drafting from KB search is unlikely to
        # help either, so the graph's conditional edge should route straight to escalation.
        confidence = 0.9 if best_hits >= 2 else (0.7 if best_hits == 1 else 0.3)
        return ClassifyResult(category=category, priority=priority, confidence=confidence)

    def draft_reply(self, title: str, context: list[str], kb_hits: list[KBHit]) -> DraftResult:
        if not kb_hits:
            return DraftResult(
                text=(
                    "Thanks for reaching out. I wasn't able to find a matching article for this "
                    "one - a specialist will follow up shortly."
                ),
                confidence=0.3,
            )
        top = kb_hits[0]
        text = f"{top.snippet} (source: {top.title})"
        # confidence mirrors the top KB hit's own match strength
        return DraftResult(text=text, confidence=min(0.95, 0.5 + top.score))


class AnthropicLLM:
    """Real model, opt-in via LLM_PROVIDER=anthropic. Uses structured output so `graph.py` gets
    the same typed result regardless of which gateway is behind it."""

    def __init__(self, api_key: str, model: str) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def classify(self, title: str, context: list[str]) -> ClassifyResult:
        prompt = (
            "Classify this support ticket. Respond with exactly three lines:\n"
            "category: billing|technical|account|general\n"
            "priority: low|medium|high\n"
            "confidence: a number between 0 and 1\n\n"
            f"Title: {title}\nContext: {' | '.join(context) or '(none)'}"
        )
        response = self._client.messages.create(
            model=self._model, max_tokens=100, messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text if response.content else ""  # type: ignore[union-attr]
        return _parse_classify(text)

    def draft_reply(self, title: str, context: list[str], kb_hits: list[KBHit]) -> DraftResult:
        kb_context = "\n".join(f"- {h.title}: {h.snippet}" for h in kb_hits) or "(no KB matches)"
        prompt = (
            "Draft a short, friendly support reply grounded only in the KB context below. "
            "End with a line 'confidence: <0..1>'.\n\n"
            f"Title: {title}\nContext: {' | '.join(context) or '(none)'}\nKB:\n{kb_context}"
        )
        response = self._client.messages.create(
            model=self._model, max_tokens=300, messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text if response.content else ""  # type: ignore[union-attr]
        return _parse_draft(text)


def _parse_classify(text: str) -> ClassifyResult:
    fields = dict(line.split(":", 1) for line in text.strip().splitlines() if ":" in line)
    category = fields.get("category", "general").strip()
    priority = fields.get("priority", "low").strip()
    try:
        confidence = float(fields.get("confidence", "0.5").strip())
    except ValueError:
        confidence = 0.5
    if category not in CATEGORIES:
        category = "general"
    return ClassifyResult(category=category, priority=priority, confidence=confidence)


def _parse_draft(text: str) -> DraftResult:
    confidence = 0.5
    lines = text.strip().splitlines()
    body_lines = []
    for line in lines:
        if line.lower().startswith("confidence:"):
            try:
                confidence = float(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        else:
            body_lines.append(line)
    return DraftResult(text="\n".join(body_lines).strip(), confidence=confidence)


def get_gateway(provider: str, api_key: str = "", model: str = "") -> LLMGateway:
    if provider == "anthropic":
        return AnthropicLLM(api_key=api_key, model=model)
    return FakeLLM()
