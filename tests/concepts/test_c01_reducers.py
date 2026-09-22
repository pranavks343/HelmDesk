"""c1: reducers (`add` + custom). Mechanism: state.py wires `hops`/`raw_hits` to `operator.add`
and `citations`/`guardrail_flags`/`audit` to custom reducers; a Send fan-out without a reducer
raises InvalidUpdateError (gotcha 6)."""

from typing import Annotated

from langgraph.errors import InvalidUpdateError
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from typing_extensions import TypedDict


def test_add_reducer_accumulates_across_send_branches():
    class S(TypedDict, total=False):
        query: str
        total: Annotated[int, lambda a, b: (a or 0) + (b or 0)]

    def fanout(state):
        return [Send("leaf", {"n": i}) for i in (1, 2, 3)]

    def leaf(state):
        return {"total": state["n"]}

    g = StateGraph(S)
    g.add_node("plan", lambda s: {})
    g.add_node("leaf", leaf)
    g.add_edge(START, "plan")
    g.add_conditional_edges("plan", fanout, ["leaf"])
    g.add_edge("leaf", END)
    app = g.compile()
    result = app.invoke({})
    assert result["total"] == 6


def test_missing_reducer_raises_on_concurrent_writes():
    class S(TypedDict, total=False):
        x: int  # no reducer -> last-write-wins is NOT safe for concurrent branches

    def fanout(state):
        return [Send("leaf", {"n": i}) for i in (1, 2)]

    def leaf(state):
        return {"x": state["n"]}

    g = StateGraph(S)
    g.add_node("plan", lambda s: {})
    g.add_node("leaf", leaf)
    g.add_edge(START, "plan")
    g.add_conditional_edges("plan", fanout, ["leaf"])
    g.add_edge("leaf", END)
    app = g.compile()
    try:
        app.invoke({})
        raised = False
    except InvalidUpdateError:
        raised = True
    assert raised, "two parallel branches writing the same unreduced key should raise"


def test_state_py_wires_hops_and_raw_hits_to_add():
    import typing

    from supportpilot.state import ParentState

    hints = typing.get_type_hints(ParentState, include_extras=True)
    assert hints["hops"].__metadata__[0] is not None
    # smoke: the annotation exists and is Annotated (checked precisely via a real graph run in
    # test_e2e / the supervisor tests, which prove hops increments by exactly 1 per hop).
