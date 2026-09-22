"""Parent graph wiring (c4, c9, c15, c17, c25, c27 and the whole architecture in agents.md §5.1)."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from langgraph.cache.memory import InMemoryCache
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.types import RetryPolicy

from supportpilot import crash
from supportpilot.context import SupportContext
from supportpilot.errors import TransientLLMError
from supportpilot.nodes.billing_wrapper import billing_agent, route_after_billing
from supportpilot.nodes.compose import compose_reply
from supportpilot.nodes.context_nodes import manage_context
from supportpilot.nodes.guard_nodes import blocked_reply, input_guardrail, output_guardrail
from supportpilot.nodes.human_review import human_review
from supportpilot.nodes.memory_nodes import load_memory, save_memory
from supportpilot.nodes.refund import execute_refund
from supportpilot.nodes.supervisor import fallback, supervisor
from supportpilot.nodes.tech_wrapper import tech_agent
from supportpilot.serde import make_serde
from supportpilot.state import ParentState
from supportpilot.subgraphs.kb_agent import build_kb_graph

_LLM_RETRY = RetryPolicy(max_attempts=3, initial_interval=0.05, retry_on=TransientLLMError)


def _crashable(name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wraps a top-level node so `SUPPORTPILOT_CRASH_AFTER=<name>` can simulate the process dying
    right as that node is entered (c5/c19 crash + resume demo). Cheap no-op unless the env var is
    set to this exact node name."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        crash.maybe_crash(name)
        return fn(*args, **kwargs)

    return wrapper


def build_graph(
    checkpointer: BaseCheckpointSaver | None = None,
    store: BaseStore | None = None,
    cache: InMemoryCache | None = None,
) -> CompiledStateGraph[ParentState, SupportContext, ParentState, ParentState]:
    g = StateGraph(ParentState, context_schema=SupportContext)

    g.add_node(
        "input_guardrail",
        _crashable("input_guardrail", input_guardrail),
        destinations=("load_memory", "blocked_reply"),
    )
    g.add_node("blocked_reply", _crashable("blocked_reply", blocked_reply))
    g.add_node("load_memory", _crashable("load_memory", load_memory))
    g.add_node("manage_context", _crashable("manage_context", manage_context))
    g.add_node(
        "supervisor",
        _crashable("supervisor", supervisor),
        retry_policy=_LLM_RETRY,
        destinations=("kb_agent", "tech_agent", "billing_agent", "fallback", "compose_reply"),
    )
    g.add_node("kb_agent", build_kb_graph())
    # tech_agent is a wrapper (not a raw compiled-subgraph node): see nodes/tech_wrapper.py for
    # why - its own Command(goto="supervisor") replaces the static edge every other specialist
    # uses, which is what lets a Command.PARENT handoff mid-loop not *also* trigger it.
    g.add_node(
        "tech_agent", _crashable("tech_agent", tech_agent), destinations=("supervisor", "billing_agent")
    )
    g.add_node("billing_agent", _crashable("billing_agent", billing_agent))
    g.add_node("fallback", _crashable("fallback", fallback))
    g.add_node(
        "human_review",
        _crashable("human_review", human_review),
        destinations=("execute_refund", "compose_reply"),
    )
    g.add_node("execute_refund", _crashable("execute_refund", execute_refund))
    g.add_node("compose_reply", _crashable("compose_reply", compose_reply), retry_policy=_LLM_RETRY)
    g.add_node(
        "output_guardrail",
        _crashable("output_guardrail", output_guardrail),
        destinations=("compose_reply", "save_memory"),
    )
    g.add_node("save_memory", _crashable("save_memory", save_memory))

    g.add_edge(START, "input_guardrail")
    g.add_edge("blocked_reply", END)
    g.add_edge("load_memory", "manage_context")
    g.add_edge("manage_context", "supervisor")

    # kb_agent returns control to the supervisor via a plain static edge (it never crosses into
    # the parent graph via Command.PARENT, so this is safe - see tech_agent's own Command(goto=)
    # above for why it can't use the same static-edge pattern).
    g.add_edge("kb_agent", "supervisor")
    g.add_edge("fallback", "compose_reply")
    g.add_conditional_edges("billing_agent", route_after_billing, ["human_review", "execute_refund"])

    g.add_edge("execute_refund", "compose_reply")
    g.add_edge("compose_reply", "output_guardrail")
    g.add_edge("save_memory", END)

    return g.compile(checkpointer=checkpointer, store=store, cache=cache)


def make_graph() -> CompiledStateGraph[ParentState, SupportContext, ParentState, ParentState]:
    """For langgraph.json (Studio, c30) - the dev server supplies its own checkpointer/store."""
    return build_graph(cache=InMemoryCache(serde=make_serde()))
