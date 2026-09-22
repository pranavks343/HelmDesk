"""input_guardrail, blocked_reply, output_guardrail (c26)."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.config import get_stream_writer
from langgraph.runtime import Runtime
from langgraph.types import Command, Overwrite

from supportpilot.context import SupportContext
from supportpilot.guardrails.input import screen
from supportpilot.guardrails.output import SAFE_TEXT, check_output
from supportpilot.state import ParentState


def _last_human(state: ParentState) -> HumanMessage | None:
    for m in reversed(state.get("messages", [])):
        if isinstance(m, HumanMessage):
            return m
    return None


def input_guardrail(state: ParentState, runtime: Runtime[SupportContext]) -> Command:
    writer = get_stream_writer()
    human = _last_human(state)
    if human is None:
        return Command(goto="load_memory")

    verdict = screen(str(human.content))
    writer({"event": "guardrail", "stage": "input", "flags": verdict.flags, "allowed": verdict.allowed})

    # Replace the message by ID: add_messages replaces (rather than appends) when the incoming
    # message's id matches an existing one (c2 demo).
    redacted = HumanMessage(content=verdict.redacted_text, id=human.id)
    update: dict = {"messages": [redacted], "guardrail_flags": verdict.flags}

    if not verdict.allowed:
        update["audit"] = ["input blocked"]
        return Command(update=update, goto="blocked_reply")

    # `hops` accumulates via an `add` reducer for the loop-ping-pong guard within one turn;
    # `Overwrite` resets it to 0 for the new turn instead of letting it grow across the whole
    # thread. draft_answer/grade/rewrite_count/low_confidence are per-turn KB-round scratch
    # fields, reset so a stale result from a previous turn can't leak into this one's routing.
    update |= {
        "hops": Overwrite(0),
        "draft_answer": "",
        "grade": None,
        "rewrite_count": 0,
        "low_confidence": False,
        "output_retry": 0,
    }
    return Command(update=update, goto="load_memory")


def blocked_reply(state: ParentState) -> dict:
    thread_ref = state.get("query") or "this conversation"
    text = (
        "I'm not able to help with that request. If you believe this is a mistake, please "
        f"contact support and reference this ticket ({thread_ref!r}) for a human follow-up."
    )
    return {
        "final_answer": text,
        "messages": [AIMessage(content=text)],
        "audit": ["blocked_reply sent"],
    }


def output_guardrail(state: ParentState) -> Command:
    writer = get_stream_writer()
    text = state.get("final_answer", "")
    route = state.get("route")
    route_next = route.next if route else None
    fails = check_output(
        text,
        route=route_next,
        citations=state.get("citations", []),
        refund=state.get("refund"),
        low_confidence=state.get("low_confidence", False),
    )
    writer({"event": "guardrail", "stage": "output", "fails": fails})

    if not fails:
        return Command(goto="save_memory")

    retry = state.get("output_retry", 0)
    if retry == 0:
        return Command(
            update={"output_retry": 1, "guardrail_flags": [f"output:{f}" for f in fails]},
            goto="compose_reply",
        )

    return Command(
        update={
            "final_answer": SAFE_TEXT,
            "messages": [AIMessage(content=SAFE_TEXT)],
            "guardrail_flags": [f"output:{f}" for f in fails],
            "audit": ["output guardrail fallback"],
        },
        goto="save_memory",
    )
