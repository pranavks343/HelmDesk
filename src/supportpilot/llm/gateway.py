"""LLMGateway protocol - the only door to model access (c16, c28)."""

from __future__ import annotations

from typing import Protocol

from langchain_core.messages import AIMessage, AnyMessage
from langchain_core.tools import BaseTool

from supportpilot.schemas import (
    Citation,
    ExtractedMemories,
    GradeResult,
    RefundProposal,
    RewrittenQuery,
    RouteDecision,
)


class LLMGateway(Protocol):
    def route(self, messages: list[AnyMessage], summary: str, profile: dict) -> RouteDecision: ...

    def grade(self, question: str, answer: str, citations: list[Citation]) -> GradeResult: ...

    def rewrite(self, question: str, missing: str | None) -> RewrittenQuery: ...

    def generate_answer(self, question: str, citations: list[Citation]) -> AIMessage: ...

    def compose_reply(self, messages: list[AnyMessage], context_blob: str) -> AIMessage: ...

    def tech_step(self, messages: list[AnyMessage], tools: list[BaseTool]) -> AIMessage: ...

    def assess_refund(self, account: dict, complaint: str) -> RefundProposal: ...

    def summarize(self, prior_summary: str, messages: list[AnyMessage]) -> str: ...

    def extract_memories(self, messages: list[AnyMessage]) -> ExtractedMemories: ...
