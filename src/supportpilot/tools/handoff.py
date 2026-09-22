"""Handoff tool (c15): reaches a parent-graph node from inside the tech subgraph."""

from __future__ import annotations

from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.types import Command


@tool
def transfer_to_billing(
    reason: str, tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """Hand the conversation to the billing agent (refunds, duplicate charges, invoices)."""
    return Command(
        goto="billing_agent",
        graph=Command.PARENT,
        update={
            # Mandatory: keeps the tool-call / tool-result pairing valid (gotcha 3).
            "messages": [ToolMessage("Transferring to billing", tool_call_id=tool_call_id)],
            "active_agent": "billing_agent",
            "audit": ["handoff tech→billing"],
        },
    )
