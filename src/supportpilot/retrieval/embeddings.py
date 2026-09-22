"""Deterministic feature-hashing embeddings so semantic memory works offline (c21)."""

from __future__ import annotations

import hashlib
import math

from langchain_core.embeddings import Embeddings

from supportpilot.retrieval.tfidf import tokenize


def _stem(tok: str) -> str:
    return tok[:-1] if len(tok) > 3 and tok.endswith("s") else tok


class HashingEmbeddings(Embeddings):
    """Signed feature-hashing bag-of-words (dims=256), L2-normalised.

    Shared tokens -> shared buckets -> similar vectors. Uses md5, never ``hash()``, so it is
    stable across processes.
    """

    def __init__(self, dims: int = 256) -> None:
        self.dims = dims

    def embed_query(self, text: str) -> list[float]:
        vec = [0.0] * self.dims
        for tok in map(_stem, tokenize(text)):
            digest = hashlib.md5(tok.encode()).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dims
            vec[idx] += 1.0 if digest[4] % 2 == 0 else -1.0
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm else vec

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(t) for t in texts]
