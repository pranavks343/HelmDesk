"""Pydantic models used as structured LLM output and as typed state values (c16)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RouteDecision(BaseModel):
    next: Literal["kb_agent", "tech_agent", "billing_agent", "compose_reply", "fallback"]
    confidence: float = Field(ge=0, le=1)
    reason: str


class GradeResult(BaseModel):
    relevant: bool
    grounded: bool
    missing: str | None = None  # what the answer lacked; feeds rewrite


class RewrittenQuery(BaseModel):
    query: str


class Citation(BaseModel):
    doc_id: str
    source: Literal["docs", "forum", "changelog"]
    title: str
    score: float
    snippet: str


class RefundProposal(BaseModel):
    invoice_id: str
    amount: float = Field(ge=0)
    currency: Literal["USD", "INR", "EUR"]
    reason: str
    auto_approvable: bool


class MemoryFact(BaseModel):
    text: str  # "Prefers email over phone"
    category: Literal["preference", "account", "issue_history"]


class ExtractedMemories(BaseModel):
    facts: list[MemoryFact]


class GuardrailVerdict(BaseModel):
    allowed: bool
    flags: list[str]
    redacted_text: str
