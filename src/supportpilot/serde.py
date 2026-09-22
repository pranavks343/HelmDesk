"""Shared serializer for checkpointers and caches: an explicit allowlist for our own Pydantic
models, instead of the default permissive-with-warning behaviour (see docs/API_NOTES.md)."""

from __future__ import annotations

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from supportpilot import schemas

ALLOWED_MODELS = [
    schemas.RouteDecision,
    schemas.GradeResult,
    schemas.RewrittenQuery,
    schemas.Citation,
    schemas.RefundProposal,
    schemas.MemoryFact,
    schemas.ExtractedMemories,
    schemas.GuardrailVerdict,
]


def make_serde() -> JsonPlusSerializer:
    return JsonPlusSerializer(allowed_msgpack_modules=ALLOWED_MODELS)
