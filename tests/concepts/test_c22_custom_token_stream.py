"""c22: custom + token streaming. Mechanism: nodes emit progress via get_stream_writer() (custom
mode); generate/compose_reply stream real AIMessageChunk tokens via GenericFakeChatModel,
filterable by metadata["langgraph_node"]."""

from tests.conftest import thread_cfg


def test_custom_events_emitted_by_guardrail_and_kb_nodes(graph, ctx):
    cfg = thread_cfg("c22-custom")
    customs = []
    # a single (non-list) stream_mode yields (namespace, chunk) pairs, not (namespace, mode, chunk)
    for _ns, chunk in graph.stream(
        {"messages": [("human", "how do I set up sso")]},
        cfg,
        context=ctx,
        stream_mode="custom",
        subgraphs=True,
    ):
        customs.append(chunk)
    events = {c.get("event") for c in customs}
    assert "guardrail" in events
    assert "retrieve" in events
    assert "merge_sources" in events


def test_token_chunks_are_filterable_by_node(graph, ctx):
    cfg = thread_cfg("c22-tokens")
    tokens_by_node = {}
    for _ns, (_msg, metadata) in graph.stream(
        {"messages": [("human", "how do I set up sso")]},
        cfg,
        context=ctx,
        stream_mode="messages",
        subgraphs=True,
    ):
        node = metadata.get("langgraph_node")
        tokens_by_node.setdefault(node, 0)
        tokens_by_node[node] += 1
    assert "generate" in tokens_by_node or "compose_reply" in tokens_by_node
