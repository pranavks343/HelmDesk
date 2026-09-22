"""Redis subscriber loop (agents.md §3: "main.py # redis subscriber loop").

Listens for `ticket.created` events published by `api` (see apps/api/routers/tickets.py), runs
each ticket through the LangGraph pipeline (graph.py), and pushes whatever the pipeline actually
produced to the notifier over gRPC - just the classify push if the graph took the low-confidence
shortcut (see graph.py's conditional edge), classify + draft if it ran the full pipeline.
"""

from __future__ import annotations

import json
import logging
from typing import Protocol

import redis

from config import settings
from graph import TicketAgentState, build_graph
from grpc_client import NotifierClient

logger = logging.getLogger("agent-worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

CHANNEL_TICKET_CREATED = "ticket.created"


class Notifier(Protocol):
    """What handle_event needs from a notifier client - just enough to swap in a test double
    without mypy requiring the concrete gRPC-backed NotifierClient."""

    def send_classify(self, state: TicketAgentState) -> object: ...

    def send_draft(self, state: TicketAgentState) -> object: ...


def handle_event(graph, notifier: Notifier, raw: str) -> None:
    try:
        event = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("dropped malformed event: %r", raw)
        return

    ticket_id = event.get("ticket_id")
    title = event.get("title", "")
    if not ticket_id:
        logger.warning("dropped event with no ticket_id: %r", event)
        return

    logger.info("triaging ticket %s: %r", ticket_id, title)
    initial_state: TicketAgentState = {
        "ticket_id": ticket_id,
        "title": title,
        "context_messages": [],
    }
    result = graph.invoke(initial_state)

    try:
        notifier.send_classify(result)
        if "draft_text" in result:
            notifier.send_draft(result)
    except Exception:
        logger.exception("failed to push triage result for ticket %s to notifier", ticket_id)
        return

    logger.info(
        "ticket %s: category=%s priority=%s auto_resolve=%s",
        ticket_id,
        result.get("category"),
        result.get("priority"),
        result.get("auto_resolve"),
    )


def run() -> None:
    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe(CHANNEL_TICKET_CREATED)
    logger.info("subscribed to %s, waiting for tickets...", CHANNEL_TICKET_CREATED)

    graph = build_graph()
    notifier = NotifierClient(settings.notifier_grpc_target)
    try:
        for message in pubsub.listen():
            if message["type"] != "message":
                continue
            handle_event(graph, notifier, message["data"])
    finally:
        notifier.close()


if __name__ == "__main__":
    run()
