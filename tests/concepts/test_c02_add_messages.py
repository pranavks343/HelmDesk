"""c2: add_messages (append, replace-by-id, remove). Mechanism: input_guardrail replaces the
human message by id after redaction; manage_context emits RemoveMessage for trimmed history."""

from langchain_core.messages import HumanMessage, RemoveMessage
from langgraph.graph.message import add_messages


def test_append_default():
    msgs = add_messages([HumanMessage(content="a", id="1")], [HumanMessage(content="b", id="2")])
    assert [m.content for m in msgs] == ["a", "b"]


def test_replace_by_id():
    msgs = add_messages([HumanMessage(content="a", id="1")], [HumanMessage(content="EDITED", id="1")])
    assert len(msgs) == 1
    assert msgs[0].content == "EDITED"


def test_remove_by_id():
    base = [HumanMessage(content="a", id="1"), HumanMessage(content="b", id="2")]
    msgs = add_messages(base, [RemoveMessage(id="1")])
    assert [m.id for m in msgs] == ["2"]


def test_input_guardrail_redacts_by_replacing_message_id(graph, ctx):
    cfg = {"configurable": {"thread_id": "c02-guard"}}
    result = graph.invoke({"messages": [("human", "email me at a@b.com")]}, cfg, context=ctx)
    humans = [m for m in result["messages"] if isinstance(m, HumanMessage)]
    assert len(humans) == 1, "redaction replaced the message in place, did not append a second one"
    assert "[EMAIL]" in humans[0].content


def test_manage_context_removes_old_messages(graph, ctx_factory):
    ctx = ctx_factory(summarize_after_messages=4)
    cfg = {"configurable": {"thread_id": "c02-trim"}}
    for i in range(6):
        graph.invoke({"messages": [("human", f"question {i} about webhooks")]}, cfg, context=ctx)
    final = graph.get_state(cfg).values
    assert final.get("summary"), "old messages were folded into the rolling summary"
    assert len(final["messages"]) < 12, "RemoveMessage actually shrank stored history"
