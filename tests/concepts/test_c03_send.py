"""c3: Send fan-out. Mechanism: kb_agent.plan_retrieval fans out to 3 parallel retrieve_source
tasks (docs/forum/changelog), asserted via the debug stream (per-task events, not just output)."""

from supportpilot.context import SupportContext
from supportpilot.subgraphs.kb_agent import build_kb_graph


def test_plan_retrieval_fans_out_three_retrieve_source_tasks():
    kb = build_kb_graph()
    task_starts = []
    for chunk in kb.stream(
        {"query": "how do backups work", "rewrite_count": 0},
        {"configurable": {"thread_id": "c03-fanout"}},
        context=SupportContext(user_id="u1"),
        stream_mode="debug",
    ):
        if isinstance(chunk, dict) and chunk.get("payload", {}).get("name") == "retrieve_source":
            task_starts.append(chunk["payload"])
    task_ids = {t.get("id") for t in task_starts if t.get("id")}
    assert len(task_ids) >= 3, f"expected >=3 distinct retrieve_source tasks, saw {len(task_ids)}"


def test_fanout_produces_hits_from_all_three_sources():
    kb = build_kb_graph()
    result = kb.invoke(
        {"query": "sso setup", "rewrite_count": 0},
        {"configurable": {"thread_id": "c03-hits"}},
        context=SupportContext(user_id="u1"),
    )
    sources_seen = {c.source for c in result["raw_hits"]}
    assert sources_seen == {"docs", "forum", "changelog"}
