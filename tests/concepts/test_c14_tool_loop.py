"""c14: tool loop. Mechanism: tools_condition routes tech_llm's tool_calls into ToolNode(TECH_TOOLS)
and back, until a final answer with no tool_calls ends the subgraph."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from supportpilot.context import SupportContext
from supportpilot.subgraphs.tech_agent import build_tech_graph
from tests.conftest import thread_cfg


def test_error_code_question_triggers_get_error_code_doc():
    tech = build_tech_graph()
    result = tech.invoke(
        {"messages": [HumanMessage(content="error E105 please help")]},
        thread_cfg("c14-error"),
        context=SupportContext(user_id="u1"),
    )
    tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_msgs) == 1
    assert tool_msgs[0].name == "get_error_code_doc"
    final = result["messages"][-1]
    assert isinstance(final, AIMessage) and not final.tool_calls


def test_order_lookup_triggers_lookup_order():
    tech = build_tech_graph()
    result = tech.invoke(
        {"messages": [HumanMessage(content="please check ORD-5001")]},
        thread_cfg("c14-order"),
        context=SupportContext(user_id="u1"),
    )
    tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert tool_msgs[0].name == "lookup_order"


def test_no_tool_calls_ends_immediately():
    tech = build_tech_graph()
    result = tech.invoke(
        {"messages": [HumanMessage(content="hello there")]},
        thread_cfg("c14-none"),
        context=SupportContext(user_id="u1"),
    )
    assert not any(isinstance(m, ToolMessage) for m in result["messages"])
