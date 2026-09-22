from supportpilot.reducers import append_unique, merge_citations
from supportpilot.schemas import Citation


def _c(doc_id, score, snippet="s"):
    return Citation(doc_id=doc_id, source="docs", title="T", score=score, snippet=snippet)


def test_merge_citations_unions_by_doc_id_keeping_higher_score():
    a = [_c("x", 0.5), _c("y", 0.9)]
    b = [_c("x", 0.9), _c("z", 0.1)]
    merged = merge_citations(a, b)
    by_id = {c.doc_id: c for c in merged}
    assert by_id["x"].score == 0.9
    assert set(by_id) == {"x", "y", "z"}


def test_merge_citations_sorted_by_score_desc():
    merged = merge_citations([_c("a", 0.1)], [_c("b", 0.9), _c("c", 0.5)])
    assert [c.score for c in merged] == [0.9, 0.5, 0.1]


def test_merge_citations_handles_none_and_empty():
    assert merge_citations(None, None) == []
    assert merge_citations([], [_c("a", 1.0)])[0].doc_id == "a"
    assert merge_citations([_c("a", 1.0)], None)[0].doc_id == "a"


def test_merge_citations_idempotent():
    a = [_c("a", 0.5)]
    b = [_c("b", 0.7)]
    once = merge_citations(a, b)
    twice = merge_citations(once, b)
    assert once == twice


def test_merge_citations_associative_on_sample_data():
    a, b, c = [_c("a", 0.3)], [_c("b", 0.6)], [_c("a", 0.9)]
    left = merge_citations(merge_citations(a, b), c)
    right = merge_citations(a, merge_citations(b, c))
    assert {x.doc_id: x.score for x in left} == {x.doc_id: x.score for x in right}


def test_append_unique_preserves_order_skips_dupes():
    assert append_unique(["a", "b"], ["b", "c", "a"]) == ["a", "b", "c"]


def test_append_unique_handles_none_and_empty():
    assert append_unique(None, None) == []
    assert append_unique(None, ["x"]) == ["x"]
    assert append_unique(["x"], None) == ["x"]


def test_append_unique_idempotent():
    once = append_unique(["a"], ["b"])
    twice = append_unique(once, ["b"])
    assert once == twice
