"""c15: supervisor + Command.PARENT handoff. Mechanism: transfer_to_billing (called from inside
the tech_agent subgraph's ToolNode) returns Command(graph=Command.PARENT, goto="billing_agent"),
reaching a node that doesn't exist in the tech subgraph's own graph."""

from langgraph.errors import ParentCommand

from supportpilot.context import SupportContext
from supportpilot.subgraphs.tech_agent import build_tech_graph
from tests.conftest import thread_cfg


def test_standalone_tech_subgraph_raises_parent_command_on_handoff():
    """Without a real parent, Command(graph=PARENT) surfaces as ParentCommand - proving the
    handoff fires; the parent graph test below proves it's actually caught and routed."""
    tech = build_tech_graph()
    try:
        tech.invoke(
            {"messages": [("human", "I think I was charged twice, no order number")]},
            thread_cfg("c15-standalone"),
            context=SupportContext(user_id="u1"),
        )
        raised = False
    except ParentCommand:
        raised = True
    assert raised


def test_parent_graph_routes_handoff_to_billing_agent(graph, ctx):
    cfg = thread_cfg("c15-parent")
    # An order id makes the supervisor's initial triage pick tech_agent; the billing phrasing
    # then makes tech_step transfer to billing once inside the loop (see llm/fake.py comments).
    result = graph.invoke(
        {"messages": [("human", "I was charged twice for order ORD-5001, please refund")]}, cfg, context=ctx
    )
    assert "handoff tech→billing" in result["audit"]
    assert result["active_agent"] == "billing_agent"
    assert result["refund"] is not None
    assert any(isinstance(m, type(result["messages"][-1])) for m in result["messages"])
