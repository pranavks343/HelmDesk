"""c21: semantic memory. Mechanism: store.search over HashingEmbeddings finds related facts for
one user and returns nothing for an unrelated/unknown user (namespace isolation)."""

from supportpilot.memory.store import facts_namespace


def test_semantic_search_finds_related_fact(store):
    store.put(facts_namespace("u_a"), "f1", {"text": "Prefers email over phone", "category": "preference"})
    store.put(
        facts_namespace("u_a"),
        "f2",
        {"text": "Has raised a billing issue before", "category": "issue_history"},
    )
    hits = store.search(facts_namespace("u_a"), query="how do they like to be contacted", limit=3)
    assert hits
    assert hits[0].value["text"] == "Prefers email over phone"


def test_semantic_search_isolated_per_user(store):
    store.put(facts_namespace("u_a"), "f1", {"text": "Prefers email over phone"})
    other_user_hits = store.search(facts_namespace("u_unrelated"), query="contact preference", limit=3)
    assert other_user_hits == []


def test_save_memory_deduplicates_near_identical_facts(graph, ctx_factory, store):
    from supportpilot.memory.store import facts_namespace as fn

    ctx = ctx_factory(user_id="u_dedupe")
    cfg = {"configurable": {"thread_id": "c21-dedupe"}}
    graph.invoke({"messages": [("human", "I prefer email, not phone, for contact")]}, cfg, context=ctx)
    graph.invoke({"messages": [("human", "again, I prefer email, not phone, for contact")]}, cfg, context=ctx)
    facts = store.search(fn("u_dedupe"), query="contact preference", limit=20)
    preference_facts = [f for f in facts if f.value.get("category") == "preference"]
    assert len(preference_facts) <= 1, "near-duplicate preference fact was not stored twice"
