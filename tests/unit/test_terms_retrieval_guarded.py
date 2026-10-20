"""Synthetic engineering checks; none of these fixtures are scientific gold."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from scripts.terms_retrieval_guarded import (
    clause,
    contextual_signals,
    corpus_weights,
    grouped_results,
    guarded_order,
    idf_weights,
    work_ids,
)
from tests.unit.test_terms_retrieval_compare import result


def test_idf_counts_duplicate_uploads_once_and_downweights_common_tokens():
    snapshot = {"articles": [
        {"article_id": "a", "doi": "10.fixture/A", "pages": [{"text": "nafion rare"}]},
        {"article_id": "copy", "doi": "10.fixture/a", "pages": [{"text": "nafion rare"}]},
        {"article_id": "b", "doi": "10.fixture/b", "pages": [{"text": "nafion other"}]},
    ]}
    contexts = {"articles": [{"article_id": a["article_id"], "terms": [{"term": "nafion"}]} for a in snapshot["articles"]]}
    weights, _ = corpus_weights(snapshot, contexts, work_ids(snapshot))
    assert weights["rare"] > weights["nafion"]
    assert weights == idf_weights({"a": {"nafion", "rare"}, "b": {"nafion", "other"}})


def test_guard_preserves_membership_and_rejects_loss_of_original_query_tokens():
    baseline = [result("1", "nafion conductivity rare"), result("2", "nafion conductivity")]
    signals = {"1": {"terms": 0.1}, "2": {"terms": 2.0}}
    ranked, diagnostic = guarded_order(baseline, "nafion conductivity rare", signals, set(), ("terms",))
    assert ranked == baseline
    assert diagnostic["fallback"] == "no_supported_swap"
    contender = replace(baseline[1], full_text=baseline[0].full_text, snippet=baseline[0].snippet)
    ranked, _ = guarded_order([baseline[0], contender], "nafion conductivity rare", signals, set(), ("terms",))
    assert [r.chunk_id for r in ranked] == ["2", "1"]
    assert {r.chunk_id for r in ranked} == {"1", "2"}


def test_fallback_locks_unsupported_slots_and_pareto_rejects_weaker_context():
    baseline = [result("1"), result("2")]
    signals = {"1": {"terms": 1.0, "tac": 0.5}, "2": {"terms": 2.0, "tac": 0.1}}
    assert guarded_order(baseline, "nafion conductivity", signals, set(), ("terms", "tac"))[0] == baseline
    assert guarded_order(baseline, "nafion conductivity", signals, {"1"}, ("terms",))[0] == baseline


def test_adequacy_change_rolls_back_without_reading_relevance_labels(monkeypatch):
    baseline = [result("1"), result("2")]
    signals = {"1": {"terms": 0.0}, "2": {"terms": 1.0}}
    answers = iter([False, True])
    monkeypatch.setattr("scripts.terms_retrieval_guarded.assess_evidence_adequacy",
                        lambda *args, **kwargs: SimpleNamespace(adequate=next(answers)))
    ranked, diagnostics = guarded_order(baseline, "nafion conductivity", signals, set(), ("terms",))
    assert ranked == baseline
    assert diagnostics["adequacy_rollback"]
    assert diagnostics["swaps_proposed"]


def fixture_contexts():
    quote = "Nafion membranes show conductivity; Later sentence."
    source = {"quote": "Nafion membranes", "start": 100, "end": 116, "page_number": 1,
              "text_layer": "original", "original_pdf_path": "fixture.pdf", "layer_pdf_path": "fixture.pdf"}
    context = {"context_id": "ctx", "kind": "A", "boundary_status": "pass",
               "source": {**source, "quote": quote, "end": 100 + len(quote), "region_id": "region"}}
    contexts = {"articles": [{"article_id": "a", "contexts": [context],
                             "terms": [{"term_id": "t", "term": "nafion membranes"}],
                             "mentions": [{"mention_id": "m", "source": source}],
                             "uses": [{"use_id": "u", "term_id": "t", "mention_id": "m", "context_id": "ctx"}]}]}
    classification = {"articles": [{"article_id": "a", "assignments": [
        {"use_id": "u", "axis": "type", "state": "proposed"}]}]}
    return quote, contexts, classification


def test_phrase_signal_requires_exact_query_phrase_and_full_source_clause():
    quote, contexts, classification = fixture_contexts()
    baseline = [result("1", quote)]
    signals, locked = contextual_signals(baseline, contexts, classification, ["nafion membranes conductivity"],
                                        {"nafion": 1.0, "membranes": 2.0, "conductivity": 2.0},
                                        {"nafion membranes": 2.0}, 2)
    assert signals["1"]["terms"] > 0
    assert not locked
    fragment = signals["1"]["term_evidence"][0]["clause"]
    assert fragment["quote"] == "Nafion membranes show conductivity"
    assert fragment["start"] == 100
    for variant, text in (("nafion", quote), ("nafion membranes conductivity", "Nafion membranes")):
        scored, _ = contextual_signals([result("1", text)], contexts, classification, [variant], {},
                                      {"nafion membranes": 2.0}, 2)
        assert scored["1"]["terms"] == 0


def test_unknown_types_and_unreviewed_contexts_supply_no_phrase_boost():
    quote, contexts, classification = fixture_contexts()
    classification["articles"][0]["assignments"][0]["state"] = "unresolved"
    scored, _ = contextual_signals([result("1", quote)], contexts, classification, ["nafion membranes"], {},
                                  {"nafion membranes": 2.0}, 2)
    assert scored["1"]["terms"] == 0
    contexts["articles"][0]["contexts"][0]["boundary_status"] = "unreviewed"
    scored, locked = contextual_signals([result("1", quote)], contexts, classification, ["nafion membranes"], {},
                                       {"nafion membranes": 2.0}, 2)
    assert scored["1"]["tac"] == 0
    assert locked == {"1"}


def test_clause_rejects_source_corruption_and_keeps_offsets():
    _, contexts, _ = fixture_contexts()
    article = contexts["articles"][0]
    with pytest.raises(ValueError, match="source mismatch"):
        clause(article["contexts"][0], {**article["mentions"][0]["source"], "start": 101})


def test_work_grouping_keeps_all_distinct_chunk_and_article_ids():
    original = result("one")
    upload = replace(result("two"), article_id="copy")
    another = replace(result("three"), article_id="b")
    groups = grouped_results([original, upload, another], {"a": "work", "copy": "work", "b": "other"})
    assert groups[0]["article_ids"] == ["a", "copy"]
    assert groups[0]["chunk_ids"] == ["one", "two"]
    assert sorted(cid for group in groups for cid in group["chunk_ids"]) == ["one", "three", "two"]
