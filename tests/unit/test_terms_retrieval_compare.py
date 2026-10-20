"""Engineering checks for the offline adapter; fixtures are not scientific gold."""
from dataclasses import replace

import pytest

from app.retrieval.search import SearchResult
from scripts.terms_retrieval_compare import common_pool, fuse, rank_terms, result_from_saved, term_signals


def result(identifier: str, text: str = "Nafion conductivity") -> SearchResult:
    return SearchResult(article_id="a", chunk_id=identifier, title="Synthetic fixture", doi=None,
                        page_start=1, page_end=1, source_type="main_text", snippet=text,
                        score=0.5, retrieval_method="fixture", full_text=text, text_layer="original")


def test_pool_preserves_baseline_prefix_and_adds_distinct_candidates():
    first, second, third = result("1"), result("2"), result("3")
    pool = common_pool([first, second], [third, second])
    assert pool == [first, second, third]
    with pytest.raises(ValueError, match="Duplicate expanded"):
        common_pool([first], [second, second])


def test_empty_channels_preserve_order_and_all_source_fields():
    pool = [result("1"), result("2"), result("3")]
    ranked = fuse(pool, {}, {}, top_k=2)
    assert [r.chunk_id for r in ranked] == ["1", "2"]
    assert [(r.full_text, r.page_start, r.text_layer) for r in ranked] == [
        (r.full_text, r.page_start, r.text_layer) for r in pool[:2]]
    with pytest.raises(ValueError, match="Invalid retrieval"):
        fuse(pool, {}, {}, top_k=0)


def fixture_terms():
    mentions = [
        {"mention_id": "m1", "source": {"quote": "conductivity", "page_number": 1, "text_layer": "original"}},
        {"mention_id": "m2", "source": {"quote": "Nafion", "page_number": 1, "text_layer": "original"}},
        {"mention_id": "m3", "source": {"quote": "Nafion", "page_number": 2, "text_layer": "original"}},
        {"mention_id": "m4", "source": {"quote": "Nafion", "page_number": 1, "text_layer": "ocr"}},
        {"mention_id": "m5", "source": {"quote": "absent exact quote", "page_number": 1, "text_layer": "original"}},
    ]
    contexts = {"articles": [{"article_id": "a", "terms": [{"term_id": "t1", "term": "conductivity"},
                                                               {"term_id": "t2", "term": "nafion"}],
                             "mentions": mentions,
                             "uses": [{"use_id": "u" + str(i), "mention_id": "m" + str(i),
                                       "term_id": "t1" if i == 1 else "t2"} for i in range(1, 6)]}]}
    classification = {"articles": [{"article_id": "a", "assignments": [
        {"use_id": "u1", "axis": "type", "state": "proposed"},
        {"use_id": "u2", "axis": "type", "state": "unresolved"},
        {"use_id": "u2", "axis": "role", "state": "proposed"},
        *({"use_id": "u" + str(i), "axis": "type", "state": "proposed"} for i in range(3, 6)),
    ]}]}
    return contexts, classification


def test_typed_signal_requires_resolved_type_same_page_layer_and_exact_quote():
    contexts, classification = fixture_terms()
    typed = term_signals([result("c")], contexts, classification, typed=True)
    all_terms = term_signals([result("c")], contexts, classification, typed=False)
    assert [r["use_id"] for r in typed["c"]] == ["u1"]
    assert [r["use_id"] for r in all_terms["c"]] == ["u1", "u2"]


def test_repeated_mentions_do_not_multiply_query_coverage():
    pool = [result("c")]
    signal = {"term_id": "t", "term": "conductivity", "use_id": "u"}
    once = rank_terms(pool, {"c": [signal]}, ["Nafion conductivity"])
    repeated = rank_terms(pool, {"c": [signal] * 5}, ["Nafion conductivity"])
    assert repeated == once
    assert once[0]["score"] == 0.5
    assert rank_terms(pool, {"c": []}, ["Nafion"]) == []


def test_saved_evidence_corruption_is_rejected():
    saved = result("c").__dict__
    source = {"text": "Nafion conductivity", "page_start": 1, "page_end": 1,
              "source_type": "main_text", "text_layer": "original"}
    chunks = {"c": ({"article_id": "a"}, source)}
    assert result_from_saved(saved, chunks).full_text == source["text"]
    with pytest.raises(ValueError, match="text differs"):
        result_from_saved({**saved, "full_text": "changed"}, chunks)
    with pytest.raises(ValueError, match="page_start"):
        result_from_saved({**saved, "page_start": 2}, chunks)


def test_terms_signal_can_displace_baseline_but_not_change_evidence():
    pool = [result("1"), replace(result("2"), full_text="Second exact fixture")]
    ranked = fuse(pool, {}, {"2": 1}, top_k=1)
    assert ranked[0].chunk_id == "2"
    assert ranked[0].full_text == "Second exact fixture"
    assert [r.chunk_id for r in pool] == ["1", "2"]
