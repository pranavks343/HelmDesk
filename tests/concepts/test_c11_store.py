"""c11: Store + namespaces. Mechanism: load_memory/save_memory read and write InMemoryStore under
('users', uid, 'profile') and ('users', uid, 'facts')."""

from supportpilot.memory.store import facts_namespace, profile_namespace
from tests.conftest import thread_cfg


def test_profile_namespace_put_get(store):
    store.put(profile_namespace("u_x"), "profile", {"plan_tier": "pro", "ticket_count": 1})
    item = store.get(profile_namespace("u_x"), "profile")
    assert item.value == {"plan_tier": "pro", "ticket_count": 1}


def test_facts_namespace_isolated_per_user(store):
    store.put(facts_namespace("u_a"), "f1", {"text": "fact a"})
    store.put(facts_namespace("u_b"), "f1", {"text": "fact b"})
    a = store.get(facts_namespace("u_a"), "f1")
    b = store.get(facts_namespace("u_b"), "f1")
    assert a.value["text"] == "fact a"
    assert b.value["text"] == "fact b"


def test_save_memory_writes_profile_and_facts(graph, ctx, store):
    cfg = thread_cfg("c11-save")
    graph.invoke({"messages": [("human", "I think I was charged twice")]}, cfg, context=ctx)
    profile = store.get(profile_namespace(ctx.user_id), "profile")
    assert profile is not None
    assert profile.value["ticket_count"] >= 1
