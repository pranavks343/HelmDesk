from supportpilot.retrieval.embeddings import HashingEmbeddings
from supportpilot.retrieval.tfidf import normalize, search, tokenize, vocabulary


def test_normalize_lowercases_and_strips_punctuation():
    assert normalize("How do I set-up SSO?!") == "how do i set up sso"


def test_tokenize_drops_stopwords_and_short_tokens():
    toks = tokenize("How do I set up SSO with Okta")
    assert "how" not in toks and "i" not in toks
    assert "sso" in toks and "okta" in toks


def test_search_ranks_relevant_doc_first():
    hits = search("how do I set up SSO with okta", "docs")
    assert hits, "expected at least one hit"
    assert hits[0].doc_id == "sso-setup"
    assert hits[0].source == "docs"


def test_search_returns_at_most_k():
    hits = search("error", "docs", k=2)
    assert len(hits) <= 2


def test_search_irrelevant_query_returns_few_or_no_hits():
    hits = search("zzyzxqqqnonexistentword", "docs")
    assert hits == []


def test_search_forum_and_changelog_sources_work():
    assert search("sso okta loop", "forum")[0].source == "forum"
    assert search("outage postmortem", "changelog")[0].source == "changelog"


def test_vocabulary_nonempty():
    assert len(vocabulary()) > 20


def test_hashing_embeddings_deterministic():
    e = HashingEmbeddings()
    a1 = e.embed_query("refund billing invoice")
    a2 = e.embed_query("refund billing invoice")
    assert a1 == a2


def test_hashing_embeddings_similar_text_more_similar():
    e = HashingEmbeddings()
    a = e.embed_query("prefers email over phone")
    b = e.embed_query("email phone contact preference")
    c = e.embed_query("refund billing invoice dispute")

    def cos(x, y):
        return sum(p * q for p, q in zip(x, y, strict=True))

    assert cos(a, b) > cos(a, c)


def test_hashing_embeddings_normalized():
    import math

    e = HashingEmbeddings()
    v = e.embed_query("some reasonably long piece of text about backups and restores")
    norm = math.sqrt(sum(x * x for x in v))
    assert abs(norm - 1.0) < 1e-6 or norm == 0.0
