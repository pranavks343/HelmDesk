"""Graph state schemas (c1, c2, c9, c17, c27)."""

from __future__ import annotations

from operator import add
from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from langgraph.managed import RemainingSteps
from typing_extensions import TypedDict

from supportpilot.reducers import append_unique, merge_citations
from supportpilot.schemas import Citation, GradeResult, RefundProposal, RouteDecision


class ParentState(TypedDict, total=False):
    # c2 - conversation
    messages: Annotated[list[AnyMessage], add_messages]
    summary: str  # c20 rolling summary

    # routing
    route: RouteDecision | None  # c16 (no reducer: last write wins)
    active_agent: str
    hops: Annotated[int, add]  # c1 built-in `add` on ints: supervisor loop counter
    budget_exhausted: bool  # c27 a subgraph ran out of steps

    # KB agent (shared with kb subgraph)
    query: str
    raw_hits: Annotated[list[Citation], add]  # c1 `add`: Send branches append
    citations: Annotated[list[Citation], merge_citations]  # c1 custom
    draft_answer: str
    grade: GradeResult | None
    rewrite_count: int
    low_confidence: bool

    # memory (c11, c21)
    profile: dict
    recalled_facts: list[str]

    # billing / HITL
    refund: RefundProposal | None
    review: dict  # {"decision": ..., "edited_reply": ...}
    refund_executed: bool

    # guardrails & audit
    guardrail_flags: Annotated[list[str], append_unique]  # c1 custom
    audit: Annotated[list[str], append_unique]
    output_retry: int

    final_answer: str
    remaining_steps: RemainingSteps  # c27 managed value


class KBState(TypedDict, total=False):
    """Subset of ParentState with the *same names and reducers* (shared-schema subgraph, c9)."""

    query: str
    raw_hits: Annotated[list[Citation], add]
    citations: Annotated[list[Citation], merge_citations]
    draft_answer: str
    grade: GradeResult | None
    rewrite_count: int
    low_confidence: bool
    audit: Annotated[list[str], append_unique]


class TechState(TypedDict, total=False):
    """Tech ReAct loop state (c14). Shares ``messages``/``audit``/``active_agent`` with the parent."""

    messages: Annotated[list[AnyMessage], add_messages]
    summary: str
    profile: dict
    recalled_facts: list[str]
    active_agent: str
    audit: Annotated[list[str], append_unique]
    budget_exhausted: bool
    remaining_steps: RemainingSteps


class BillingState(TypedDict):
    """Private billing schema - deliberately *disjoint* from ParentState (c17)."""

    customer_id: str
    complaint: str
    account: dict
    invoices: list[dict]
    proposal: RefundProposal | None
