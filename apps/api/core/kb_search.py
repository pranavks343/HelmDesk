"""Keyword search over a small in-repo KB corpus.

Chose keyword search over pgvector for this project (§6 of agents.md explicitly says "pick one,
document why"): pgvector needs an embedding model (API cost/latency, or a local model dependency)
just to answer "what's your refund policy" - overkill at this KB's size (a handful of articles).
Plain TF-style keyword overlap is deterministic, needs no extra infra beyond what's already
running, and is easy to reason about in an interview. The documented production upgrade path is
pgvector + a real embedding model once the KB grows past what keyword matching handles well
(paraphrased queries, multi-lingual, etc).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

KB_DIR = Path(__file__).resolve().parent.parent / "kb_data"
STOPWORDS = frozenset("a an the is are was were do does how what why for to of in on and or".split())


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


def search(query: str, k: int = 3) -> list[KBHit]:
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
