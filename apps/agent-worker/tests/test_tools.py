from tools import kb_search, priority_score, sentiment


def test_kb_search_finds_relevant_article():
    hits = kb_search("how do I set up sso with okta")
    assert hits
    assert hits[0].doc_id == "sso-setup"


def test_kb_search_no_match_returns_empty():
    assert kb_search("zzznonexistentqueryxyz") == []


def test_kb_search_respects_k():
    hits = kb_search("api", k=1)
    assert len(hits) <= 1


def test_sentiment_negative():
    assert sentiment("this is broken and I am furious, terrible service") == "negative"


def test_sentiment_positive():
    assert sentiment("thanks, this works great, appreciate it") == "positive"


def test_sentiment_neutral():
    assert sentiment("how do I reset my password") == "neutral"


def test_priority_urgent_keyword():
    assert priority_score("URGENT: api is down", "neutral") == "high"


def test_priority_negative_sentiment():
    assert priority_score("my dashboard is confusing", "negative") == "medium"


def test_priority_default_low():
    assert priority_score("how do I export my data", "neutral") == "low"
