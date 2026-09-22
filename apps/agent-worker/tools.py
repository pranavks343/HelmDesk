"""Agent tools: kb_search, sentiment, priority_score (agents.md §3, §8).

`kb_search` deliberately keeps its own small copy of the KB corpus rather than calling `api`'s
`/kb/search` over HTTP - a worker reaching into another service's internals (or even its REST
API) for every ticket would couple a background job's latency/availability to the request-serving
API; a local read-only copy of a small, slow-changing corpus is the simpler and more resilient
choice at this scale. (Production upgrade path: a shared KB service or a synced read replica.)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

KB_DIR = Path(__file__).resolve().parent / "kb_data"
STOPWORDS = frozenset("a an the is are was were do does how what why for to of in on and or".split())

NEGATIVE_WORDS = frozenset(
    "angry furious broken down outage urgent critical asap unacceptable terrible awful "
    "frustrated failed failing crash crashed lost".split()
)
POSITIVE_WORDS = frozenset("thanks thank great awesome resolved works working love appreciate".split())
URGENT_WORDS = frozenset("urgent asap critical down outage emergency immediately".split())


@dataclass(frozen=True)
class KBHit:
    doc_id: str
    title: str
    snippet: str
    score: float


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


@lru_cache(maxsize=1)
def _corpus() -> list[tuple[str, str, str, set[str]]]:
    docs = []
    for path in sorted(KB_DIR.glob("*.txt")):
        text = path.read_text()
        title_line, _, body = text.partition("\n")
        title = title_line.removeprefix("title:").strip()
        docs.append((path.stem, title, body.strip(), _tokenize(title + " " + body)))
    return docs


def kb_search(query: str, k: int = 3) -> list[KBHit]:
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []
    scored = []
    for doc_id, title, body, tokens in _corpus():
        overlap = q_tokens & tokens
        if not overlap:
            continue
        score = len(overlap) / len(q_tokens)
        snippet = body[:200] + ("..." if len(body) > 200 else "")
        scored.append(KBHit(doc_id=doc_id, title=title, snippet=snippet, score=round(score, 3)))
    scored.sort(key=lambda h: -h.score)
    return scored[:k]


def sentiment(text: str) -> str:
    """Very small lexicon-based sentiment classifier - deterministic and offline. A real system
    would use a proper model; this is enough to demonstrate the pipeline stage and is easy to
    reason about/debug in an interview."""
    tokens = _tokenize(text)
    neg = len(tokens & NEGATIVE_WORDS)
    pos = len(tokens & POSITIVE_WORDS)
    if neg > pos:
        return "negative"
    if pos > neg:
        return "positive"
    return "neutral"


def priority_score(title: str, sentiment_label: str) -> str:
    """Heuristic priority: urgent-language or negative sentiment escalates the ticket."""
    tokens = _tokenize(title)
    if tokens & URGENT_WORDS:
        return "high"
    if sentiment_label == "negative":
        return "medium"
    return "low"
