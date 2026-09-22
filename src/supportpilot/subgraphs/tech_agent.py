"""Tech agent: a tool-calling ReAct loop that can hand off to billing mid-conversation.

Concepts: Tool loop (c14), Supervisor + handoffs via Command.PARENT (c15).
"""

from __future__ import annotations

from langchain_core.messages import AIMessage
from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.runtime import Runtime
from langgraph.types import RetryPolicy

from supportpilot.context import SupportContext
from supportpilot.errors import TransientLLMError
from supportpilot.llm.factory import get_gateway
from supportpilot.memory.short_term import llm_view
from supportpilot.state import TechState
from supportpilot.tools import TECH_TOOLS

# Below this many remaining steps, stop calling tools and force a final answer instead - this is
# what lets a runaway tool loop (fake_behavior="tool_loop", or a real model that won't stop
# calling tools) degrade gracefully via RemainingSteps (c27) rather than eventually hitting
# GraphRecursionError. The hard recursion_limit is a last line of defence, not the primary guard.
DEGRADE_BELOW_STEPS = 3


def tech_llm(state: TechState, runtime: Runtime[SupportContext]) -> dict:
    remaining = state.get("remaining_steps")
    if remaining is not None and remaining < DEGRADE_BELOW_STEPS:
        text = "I'm having trouble resolving this automatically. I'm looping you in a human specialist."
        return {"messages": [AIMessage(content=text)], "active_agent": "tech_agent", "budget_exhausted": True}

    gateway = get_gateway(runtime.context)
    view = llm_view(
        state.get("messages", []),
        state.get("summary", ""),
        state.get("recalled_facts", []),
        max_tokens=runtime.context.max_context_tokens,
    )
    ai = gateway.tech_step(view, TECH_TOOLS)
    return {"messages": [ai], "active_agent": "tech_agent"}


def build_tech_graph() -> CompiledStateGraph[TechState, SupportContext, TechState, TechState]:
    g = StateGraph(TechState, context_schema=SupportContext)
    g.add_node(
        "tech_llm",
        tech_llm,
        retry_policy=RetryPolicy(max_attempts=3, initial_interval=0.05, retry_on=TransientLLMError),
    )
    g.add_node("tools", ToolNode(TECH_TOOLS))
    g.add_edge(START, "tech_llm")
    g.add_conditional_edges("tech_llm", tools_condition)
    g.add_edge("tools", "tech_llm")
    return g.compile()
