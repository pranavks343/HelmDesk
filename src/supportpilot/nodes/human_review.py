"""human_review: two sequential interrupts in one node (c7, c18)."""

from __future__ import annotations

from langgraph.types import Command, interrupt

from supportpilot.state import ParentState


def default_reply(decision: str, refund) -> str:  # noqa: ANN001 - RefundProposal | None
    if decision == "approve" and refund is not None:
        return (
            f"Good news - your refund of {refund.amount} {refund.currency} for invoice "
            f"{refund.invoice_id} has been approved and is on its way."
        )
    return (
        "We looked into your refund request and are not able to approve it at this time. "
        "A specialist will follow up with more detail."
    )


def human_review(state: ParentState) -> Command:
    """Re-runs from the top on every resume (gotcha 1): nothing above the first ``interrupt()``
    may have side effects. Resume values are matched to interrupts *by order* - approve/reject
    first, the edited reply text second."""
    refund = state.get("refund")

    decision = interrupt({"type": "approve_refund", "proposal": refund.model_dump() if refund else None})
    if decision not in ("approve", "reject"):
        raise ValueError(f"human_review: unexpected resume value for approval: {decision!r}")

    edited = interrupt({"type": "edit_reply", "draft": default_reply(decision, refund)})

    return Command(
        update={
            "review": {"decision": decision, "edited_reply": edited or None},
            "audit": [f"human review: {decision}"],
        },
        goto="execute_refund" if decision == "approve" else "compose_reply",
    )
