"""AnthropicGateway: the real model, opt-in via SUPPORTPILOT_LLM=anthropic (c28)."""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from supportpilot.schemas import (
    Citation,
    ExtractedMemories,
    GradeResult,
    RefundProposal,
    RewrittenQuery,
    RouteDecision,
)


class AnthropicGateway:
    """Talks to a real Claude model. Structured methods use `.with_structured_output`."""

    def __init__(self, model_name: str) -> None:
        self.model = ChatAnthropic(model=model_name, temperature=0)

    def route(self, messages: list[AnyMessage], summary: str, profile: dict) -> RouteDecision:
        sys = SystemMessage(
            content=(
                "You are a support-desk router. Read the conversation and pick exactly one "
                "destination: kb_agent (informational questions), tech_agent (errors, outages, "
                "orders), billing_agent (refunds, charges, invoices), compose_reply (greetings / "
                "closings), or fallback (unclear input).\n"
                f"Known profile: {profile}\nRolling summary: {summary}"
            )
        )
        structured = self.model.with_structured_output(RouteDecision)
        result = structured.invoke([sys, *messages])
        return result  # type: ignore[return-value]

    def grade(self, question: str, answer: str, citations: list[Citation]) -> GradeResult:
        sys = SystemMessage(
            content="Grade whether the answer is relevant to the question and grounded in the "
            "given citations. Be strict."
        )
        structured = self.model.with_structured_output(GradeResult)
        prompt = f"Question: {question}\nAnswer: {answer}\nCitations: {[c.doc_id for c in citations]}"
        result = structured.invoke([sys, HumanMessage(content=prompt)])
        return result  # type: ignore[return-value]

    def rewrite(self, question: str, missing: str | None) -> RewrittenQuery:
        sys = SystemMessage(content="Rewrite the search query to find what is missing.")
        structured = self.model.with_structured_output(RewrittenQuery)
        prompt = f"Original question: {question}\nMissing: {missing}"
        result = structured.invoke([sys, HumanMessage(content=prompt)])
        return result  # type: ignore[return-value]

    def generate_answer(self, question: str, citations: list[Citation]) -> AIMessage:
        sys = SystemMessage(
            content="Answer the question grounded ONLY in the given citations. Cite sources "
            "inline as [doc_id]."
        )
        cites = "\n".join(f"[{c.doc_id}] {c.title}: {c.snippet}" for c in citations)
        prompt = f"Question: {question}\nSources:\n{cites}"
        result = self.model.invoke([sys, HumanMessage(content=prompt)])
        return result  # type: ignore[return-value]

    def compose_reply(self, messages: list[AnyMessage], context_blob: str) -> AIMessage:
        sys = SystemMessage(
            content=f"Compose a concise, friendly final reply to the customer using this "
            f"context:\n{context_blob}"
        )
        result = self.model.invoke([sys, *messages])
        return result  # type: ignore[return-value]

    def tech_step(self, messages: list[AnyMessage], tools: list[BaseTool]) -> AIMessage:
        bound = self.model.bind_tools(tools)
        result = bound.invoke(messages)
        return result  # type: ignore[return-value]

    def assess_refund(self, account: dict, complaint: str) -> RefundProposal:
        sys = SystemMessage(
            content="Assess whether a refund is warranted given the account and complaint. "
            "auto_approvable should be true only if amount <= 20."
        )
        structured = self.model.with_structured_output(RefundProposal)
        prompt = f"Account: {account}\nComplaint: {complaint}"
        result = structured.invoke([sys, HumanMessage(content=prompt)])
        return result  # type: ignore[return-value]

    def summarize(self, prior_summary: str, messages: list[AnyMessage]) -> str:
        sys = SystemMessage(content="Extend the rolling summary with the new messages. Be terse.")
        prompt = f"Prior summary: {prior_summary}\nNew messages: {messages}"
        result = self.model.invoke([sys, HumanMessage(content=prompt)])
        return str(result.content)

    def extract_memories(self, messages: list[AnyMessage]) -> ExtractedMemories:
        sys = SystemMessage(content="Extract durable facts about the customer worth remembering.")
        structured = self.model.with_structured_output(ExtractedMemories)
        result = structured.invoke([sys, *messages])
        return result  # type: ignore[return-value]
