"""FakeGateway: deterministic, rule-based, offline. The default gateway (c28)."""

from __future__ import annotations

import re
from typing import Literal, cast

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool

from supportpilot.retrieval.tfidf import vocabulary
from supportpilot.schemas import (
    Citation,
    ExtractedMemories,
    GradeResult,
    MemoryFact,
    RefundProposal,
    RewrittenQuery,
    RouteDecision,
)

_COMMON_WORDS = frozenset(
    "is are was were be been being do does did can could will would should i you he she it we "
    "they my your his her its our their this that these those and or but if then than with "
    "for from to of in on at by about please help need want get got working right now today "
    "yesterday am pm the a an s".split()
)

ORDER_RE = re.compile(r"\bORD-\d+\b", re.I)
INVOICE_RE = re.compile(r"\bINV-\d+\b", re.I)
ERROR_CODE_RE = re.compile(r"\bE\d{3}\b", re.I)

_BILLING_WORDS = ("refund", "charge", "charged", "invoice", "billing", "billed", "payment")
_TECH_WORDS = ("error", "outage", "down", "status", "order", "bug", "crash", "not working")
_KB_WORDS = ("how", "what", "why", "setup", "set up", "configure", "docs", "explain")
_GREETING_WORDS = ("hello", "hi", "hey", "thanks", "thank you", "bye")
_BAD_ANSWER_MARKER = "​"  # zero-width marker: invisible to guardrails, detectable by grade()


def _last_human_text(messages: list[AnyMessage]) -> str:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return str(m.content)
    return ""


def _fake_stream(text: str) -> AIMessage:
    """Return an AIMessage produced via GenericFakeChatModel so `messages` stream mode yields
    real token chunks with no network (c22)."""
    model = GenericFakeChatModel(messages=iter([AIMessage(content=text)]))
    result = model.invoke("go")
    return cast(AIMessage, result)


class FakeGateway:
    """Rule-based deterministic gateway. Structured methods return real Pydantic instances so
    validation is exercised either way."""

    def __init__(self, fake_behavior: Literal["normal", "tool_loop", "bad_answer"] = "normal") -> None:
        self.fake_behavior = fake_behavior
        self._bad_answer_used = False

    # -- routing (c12, c16) ------------------------------------------------
    def route(self, messages: list[AnyMessage], summary: str, profile: dict) -> RouteDecision:
        text = _last_human_text(messages).lower()
        if not text.strip() or len(text.split()) <= 1:
            return RouteDecision(next="fallback", confidence=0.3, reason="empty or gibberish input")
        # A concrete technical artifact (order id / error code) is a stronger initial-triage
        # signal than vague billing language, so it's checked first: e.g. "charged twice for
        # order ORD-5001" starts in tech_agent, which can still transfer_to_billing mid-loop
        # (c15) once it has looked at the order.
        if ORDER_RE.search(text) or ERROR_CODE_RE.search(text):
            return RouteDecision(next="tech_agent", confidence=0.85, reason="order/error code referenced")
        if any(w in text for w in _BILLING_WORDS):
            return RouteDecision(next="billing_agent", confidence=0.9, reason="billing keyword matched")
        if any(w in text for w in _TECH_WORDS):
            return RouteDecision(next="tech_agent", confidence=0.85, reason="technical keyword matched")
        if any(w in text for w in _KB_WORDS):
            return RouteDecision(next="kb_agent", confidence=0.8, reason="informational question")
        if any(w in text for w in _GREETING_WORDS):
            return RouteDecision(next="compose_reply", confidence=0.95, reason="greeting or closing")
        if not re.search(r"[a-z]{3,}", text):
            return RouteDecision(next="fallback", confidence=0.2, reason="gibberish input")
        # Nothing matched a keyword list and no word in the message is a real word from our own
        # KB vocabulary or a common English function word either - almost certainly gibberish
        # ("asdkjaslkdj qweqwe"), not an off-keyword-but-real question.
        tokens = set(re.findall(r"[a-z]+", text))
        if not (tokens & (vocabulary() | _COMMON_WORDS)):
            return RouteDecision(next="fallback", confidence=0.2, reason="no recognizable words")
        return RouteDecision(next="kb_agent", confidence=0.55, reason="default to knowledge base")

    # -- KB agent (c13) ------------------------------------------------------
    def grade(self, question: str, answer: str, citations: list[Citation]) -> GradeResult:
        if _BAD_ANSWER_MARKER in answer:
            return GradeResult(relevant=False, grounded=False, missing="more specific citations")
        if not citations:
            return GradeResult(relevant=False, grounded=False, missing="no supporting sources found")
        return GradeResult(relevant=True, grounded=True, missing=None)

    def rewrite(self, question: str, missing: str | None) -> RewrittenQuery:
        extra = missing or "more detail"
        return RewrittenQuery(query=f"{question} {extra}".strip())

    def generate_answer(self, question: str, citations: list[Citation]) -> AIMessage:
        if self.fake_behavior == "bad_answer" and not self._bad_answer_used:
            self._bad_answer_used = True
            return _fake_stream(f"I think this might be related, but I'm guessing.{_BAD_ANSWER_MARKER}")
        if not citations:
            return _fake_stream(
                "I couldn't find anything relevant in the knowledge base for that question."
            )
        top = citations[:3]
        cite_str = " ".join(f"[{c.doc_id}]" for c in top)
        lead = top[0].snippet
        text = f"{lead} {cite_str}"
        return _fake_stream(text)

    # -- tech agent (c14, c15) ----------------------------------------------
    def tech_step(self, messages: list[AnyMessage], tools: list[BaseTool]) -> AIMessage:
        last = messages[-1] if messages else None
        if isinstance(last, ToolMessage):
            # We already have a tool result (or are looping in tool_loop mode); answer or loop.
            if self.fake_behavior == "tool_loop":
                return AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "check_service_status", "args": {"service": "api"}, "id": "loop-call"}
                    ],
                )
            return _fake_stream(f"Here's what I found: {last.content}")

        text = _last_human_text(messages)
        if self.fake_behavior == "tool_loop":
            return AIMessage(
                content="",
                tool_calls=[
                    {"name": "check_service_status", "args": {"service": "api"}, "id": "loop-call-0"}
                ],
            )
        # Explicit billing/refund language wins over a merely-referenced order id: once inside
        # the tech loop, "I was charged twice for order ORD-5001" should hand off to billing
        # rather than just looking the order up (c15). route() uses the opposite priority for
        # *initial* triage - see FakeGateway.route for why.
        if any(w in text.lower() for w in ("charged twice", "refund", "duplicate charge", "billing")):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "transfer_to_billing",
                        "args": {"reason": text[:200]},
                        "id": "call-transfer",
                    }
                ],
            )
        if m := ORDER_RE.search(text):
            return AIMessage(
                content="",
                tool_calls=[{"name": "lookup_order", "args": {"order_id": m.group()}, "id": "call-order"}],
            )
        if m := ERROR_CODE_RE.search(text):
            return AIMessage(
                content="",
                tool_calls=[
                    {"name": "get_error_code_doc", "args": {"code": m.group()}, "id": "call-error"}
                ],
            )
        if any(w in text.lower() for w in ("down", "outage", "status")):
            return AIMessage(
                content="",
                tool_calls=[
                    {"name": "check_service_status", "args": {"service": "api"}, "id": "call-status"}
                ],
            )
        return _fake_stream("Could you share an order id or error code so I can look into this?")

    # -- billing (c17) --------------------------------------------------------
    def assess_refund(self, account: dict, complaint: str) -> RefundProposal:
        invoices = account.get("invoices", [])
        dup = next((i for i in invoices if i.get("duplicate_charge")), None)
        target = dup or (invoices[0] if invoices else None)
        if target is None:
            return RefundProposal(
                invoice_id="UNKNOWN", amount=0.0, currency="USD", reason="no invoice on file",
                auto_approvable=True,
            )
        amount = target["amount"]
        return RefundProposal(
            invoice_id=target["invoice_id"],
            amount=amount,
            currency=target["currency"],
            reason="duplicate charge" if dup else complaint[:120] or "customer requested refund",
            auto_approvable=amount <= 20.0,
        )

    # -- reply composition ----------------------------------------------------
    def compose_reply(self, messages: list[AnyMessage], context_blob: str) -> AIMessage:
        return _fake_stream(context_blob)

    # -- memory (c11, c20, c21) ------------------------------------------------
    def summarize(self, prior_summary: str, messages: list[AnyMessage]) -> str:
        topics = []
        for m in messages:
            if isinstance(m, HumanMessage):
                snippet = str(m.content).strip().split("\n")[0][:60]
                if snippet:
                    topics.append(snippet)
        joined = "; ".join(topics[-5:])
        if prior_summary:
            return f"{prior_summary} | {joined}".strip(" |")
        return joined

    def extract_memories(self, messages: list[AnyMessage]) -> ExtractedMemories:
        facts: list[MemoryFact] = []
        for m in messages:
            if not isinstance(m, HumanMessage):
                continue
            text = str(m.content).lower()
            if "email" in text and "prefer" in text:
                facts.append(MemoryFact(text="Prefers email over phone", category="preference"))
            if ORDER_RE.search(text):
                oid = ORDER_RE.search(text).group().upper()  # type: ignore[union-attr]
                facts.append(MemoryFact(text=f"Referenced order {oid}", category="account"))
            if any(w in text for w in _BILLING_WORDS):
                facts.append(MemoryFact(text="Has raised a billing issue before", category="issue_history"))
        return ExtractedMemories(facts=facts)
