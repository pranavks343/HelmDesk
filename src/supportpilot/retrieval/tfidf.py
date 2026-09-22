"""In-repo TF-IDF retriever with cosine similarity, one index per source (no vector DB needed)."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, cast

from supportpilot.config import KB_DIR, KB_SOURCES
from supportpilot.schemas import Citation

STOPWORDS = frozenset(
    "a an and are as at be but by can do does for from how i if in is it its me my of on or our "
    "so that the their there this to was we what when where which who why will with you your "
    "have has had not no yes please help need want get".split()
)

# Incremented on every real search; the c23 test uses it to prove cache hits skip the retriever.
SEARCH_CALLS: Counter[str] = Counter()


def normalize(text: str) -> str:
    """Lowercase + strip punctuation. Also used to build cache keys (c23)."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", text.lower())).strip()


def tokenize(text: str) -> list[str]:
    return [t for t in normalize(text).split() if t not in STOPWORDS and len(t) > 1]


@dataclass(frozen=True)
class _Doc:
    doc_id: str
    source: str
    title: str
    body: str


def _parse(path_text: str) -> tuple[dict[str, str], str]:
    _, front, body = path_text.split("---", 2)
    meta = dict(line.split(":", 1) for line in front.strip().splitlines())
    return {k.strip(): v.strip() for k, v in meta.items()}, body.strip()


class TfidfIndex:
    def __init__(self, docs: list[_Doc]) -> None:
        self.docs = docs
        n = len(docs)
        tokenized = [tokenize(f"{d.title} {d.body}") for d in docs]
        df: Counter[str] = Counter(t for toks in tokenized for t in set(toks))
        self.idf = {t: math.log((1 + n) / (1 + c)) + 1 for t, c in df.items()}
        self.vecs = [self._vec(toks) for toks in tokenized]

    def _vec(self, tokens: list[str]) -> dict[str, float]:
        tf = Counter(tokens)
        vec = {t: c * self.idf.get(t, 0.0) for t, c in tf.items() if t in self.idf}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    def search(self, query: str, k: int = 3) -> list[tuple[_Doc, float]]:
        q = self._vec(tokenize(query))
        pairs = zip(self.docs, self.vecs, strict=True)
        scored = [(d, sum(w * v.get(t, 0.0) for t, w in q.items())) for d, v in pairs]
        scored = [(d, s) for d, s in scored if s > 0]
        return sorted(scored, key=lambda x: (-x[1], x[0].doc_id))[:k]


@lru_cache(maxsize=1)
def _indexes() -> dict[str, TfidfIndex]:
    by_source: dict[str, list[_Doc]] = {s: [] for s in KB_SOURCES}
    for src in KB_SOURCES:
        for path in sorted((KB_DIR / src).glob("*.md")):
            meta, body = _parse(path.read_text())
            by_source[src].append(_Doc(meta["id"], src, meta["title"], body))
    return {s: TfidfIndex(d) for s, d in by_source.items()}


@lru_cache(maxsize=1)
def vocabulary() -> frozenset[str]:
    return frozenset(t for idx in _indexes().values() for t in idx.idf)


def search(query: str, source: str, k: int = 3) -> list[Citation]:
    SEARCH_CALLS[source] += 1
    out = []
    for doc, score in _indexes()[source].search(query, k):
        snippet = doc.body[:160].rsplit(" ", 1)[0] + "..."
        out.append(
            Citation(
                doc_id=doc.doc_id,
                source=cast(Literal["docs", "forum", "changelog"], doc.source),
                title=doc.title,
                score=round(score, 4),
                snippet=snippet,
            )
        )
    return out
