"""gRPC client: agent-worker pushes its already-computed triage/draft results to the notifier's
TicketAgent service (agents.md §2/§7). See proto/ticket.proto for why both calls share one
request message and what the response actually means (a delivery ack, not a second computation)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "pb"))

import grpc  # noqa: E402
import ticket_pb2  # noqa: E402
import ticket_pb2_grpc  # noqa: E402

from graph import TicketAgentState  # noqa: E402


def _kb_hits_to_proto(state: TicketAgentState) -> list[ticket_pb2.KBHit]:
    return [
        ticket_pb2.KBHit(doc_id=h.doc_id, title=h.title, snippet=h.snippet, score=h.score)
        for h in state.get("kb_hits", [])
    ]


class NotifierClient:
    def __init__(self, target: str) -> None:
        self._channel = grpc.insecure_channel(target)
        self._stub = ticket_pb2_grpc.TicketAgentStub(self._channel)

    def send_classify(self, state: TicketAgentState) -> ticket_pb2.ClassifyResponse:
        request = ticket_pb2.TicketRequest(
            ticket_id=state["ticket_id"],
            title=state.get("title", ""),
            context_messages=state.get("context_messages", []),
            category=state.get("category", ""),
            priority=state.get("priority", ""),
            classify_confidence=state.get("classify_confidence", 0.0),
        )
        return self._stub.ClassifyTicket(request, timeout=5.0)

    def send_draft(self, state: TicketAgentState) -> ticket_pb2.DraftResponse:
        request = ticket_pb2.TicketRequest(
            ticket_id=state["ticket_id"],
            title=state.get("title", ""),
            context_messages=state.get("context_messages", []),
            category=state.get("category", ""),
            kb_hits=_kb_hits_to_proto(state),
            draft_text=state.get("draft_text", ""),
            draft_confidence=state.get("draft_confidence", 0.0),
            auto_resolve=state.get("auto_resolve", False),
        )
        return self._stub.DraftReply(request, timeout=5.0)

    def close(self) -> None:
        self._channel.close()
