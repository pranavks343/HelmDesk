"""Parent-graph wrapper around the tech subgraph.

Unlike kb_agent, tech_agent can issue a `Command(graph=Command.PARENT)` handoff from deep inside
its own ReAct loop (`tools/handoff.py`, c15). Embedding the tech subgraph directly as
`add_node("tech_agent", build_tech_graph())` alongside a *static* `add_edge("tech_agent",
"supervisor")` does not reliably suppress that static edge when the handoff fires in this
langgraph version: the parent-crossing `Command` gets applied as an *extra* task (correctly
landing on `billing_agent`) but the subgraph-as-node's own now-empty completion *also* satisfies
the static edge, so `supervisor` (and everything after it) runs a second, spurious time. Wrapping
tech_agent as a plain function that `.invoke()`s the subgraph and returns its own explicit
`Command(goto="supervisor", ...)` avoids the static edge entirely - a genuine `ParentCommand`
raised from `transfer_to_billing` still propagates straight through this wrapper's `.invoke()`
call to the parent Pregel loop, since Python exceptions aren't stopped by a wrapper function."""

from __future__ import annotations

from langgraph.runtime import Runtime
from langgraph.types import Command

from supportpilot.context import SupportContext
from supportpilot.state import ParentState, TechState
from supportpilot.subgraphs.tech_agent import build_tech_graph

_tech_graph = build_tech_graph()


def tech_agent(state: ParentState, runtime: Runtime[SupportContext]) -> Command:
    tech_state: TechState = {
        "messages": state.get("messages", []),
        "summary": state.get("summary", ""),
        "profile": state.get("profile", {}),
        "recalled_facts": state.get("recalled_facts", []),
        "active_agent": state.get("active_agent", "tech_agent"),
        "audit": [],
        "budget_exhausted": False,
    }
    result = _tech_graph.invoke(tech_state, context=runtime.context)
    # Only forward the keys tech_agent actually owns/changed - `messages` (add_messages already
    # dedupes/merges by id) and the bookkeeping fields it may have set.
    update = {
        "messages": result.get("messages", []),
        "active_agent": result.get("active_agent", "tech_agent"),
        "audit": result.get("audit", []),
    }
    if result.get("budget_exhausted"):
        update["budget_exhausted"] = True
    return Command(update=update, goto="supervisor")
