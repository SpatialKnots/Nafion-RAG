from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.retrieval.cross_lingual import build_query_bundle
from app.retrieval.search import SearchResult, _rerank_cross_lingual_results
from scripts.retrieval_window_selection import assess_source, in_scope, rerank_window, sentence_spans

ROOT = Path(__file__).resolve().parents[2]
CONTROLS = json.loads((ROOT / "docs/records/retrieval_window_selection_controls_v0.1.json").read_bytes())


@pytest.mark.parametrize("control", CONTROLS["controls"], ids=lambda row: row["id"])
def test_frozen_development_controls(control):
    result = assess_source(control["text"])
    assert result["body_coverage"] == control["body"]
    assert result["local_relation"] == control["local"]
    for region in result["regions"]:
        assert control["text"][region["start"] : region["end"]] == region["exact_text"]


def row(identity, text, title="Unknown", article="article"):
    return SearchResult(
        article_id=article,
        chunk_id=identity,
        title=title,
        doi=None,
        page_start=1,
        page_end=2,
        source_type="article",
        text_layer="original",
        snippet=text,
        full_text=text,
        score=1.0,
        retrieval_method="frozen",
    )


@pytest.mark.parametrize(
    "question", ["Nafion morphology", "How do solvents affect Nafion membranes?", "Как меняется набухание H-Nafion и Li-Nafion?"]
)
def test_out_of_scope_is_exact_noop(question):
    rows = [row("a", "Nafion morphology"), row("b", "Solvent conductivity")]
    bundle = build_query_bundle(question)
    expected = _rerank_cross_lingual_results(rows, bundle, window_size=1)
    actual = rerank_window(rows, bundle, window_size=1, qualifier="local_relation")
    assert asdict(actual) == asdict(expected)


@pytest.mark.parametrize("qualifier", ["body_coverage", "local_relation"])
def test_fixed_window_source_identity_and_title_isolation(qualifier):
    raw = CONTROLS["controls"][0]["text"]
    rows = [row("distractor", "Solvent conductivity", title=raw), row("source", raw, article="second")]
    before = [asdict(item) for item in rows]
    result = rerank_window(rows, build_query_bundle(CONTROLS["question"]), window_size=1, qualifier=qualifier)
    assert result.metadata["selected_window_chunk_ids"] == ["source"]
    assert result.results[0] is rows[1]
    assert {id(item) for item in result.results} == {id(item) for item in rows}
    assert [asdict(item) for item in rows] == before


def test_stable_priority_preserves_existing_order_without_qualified_sources():
    rows = [row("a", "Unrelated source"), row("b", "Unrelated source", article="second")]
    bundle = build_query_bundle(CONTROLS["question"])
    baseline = _rerank_cross_lingual_results(rows, bundle, window_size=1)
    result = rerank_window(rows, bundle, window_size=1, qualifier="local_relation")
    assert result.results == baseline.results


def test_no_raw_text_does_not_use_snippet():
    item = row("a", CONTROLS["controls"][0]["text"])
    item = replace(item, full_text=None)
    result = rerank_window([item], build_query_bundle(CONTROLS["question"]), window_size=1, qualifier="body_coverage")
    assert result.metadata["qualified_chunk_ids"] == []


def test_raw_decimal_span_and_paragraph_boundary():
    text = "At 2.5 wt%: test.\n\nNext sentence!"
    assert [text[start:end] for start, end in sentence_spans(text)] == ["At 2.5 wt%: test.", "Next sentence!"]


def test_duplicate_candidate_is_rejected():
    item = row("a", "Nafion")
    with pytest.raises(ValueError, match="Duplicate chunk"):
        rerank_window([item, item], build_query_bundle(CONTROLS["question"]), window_size=1, qualifier="local_relation")


@pytest.mark.parametrize("qualifier,window", [("invalid", 1), ("local_relation", 0)])
def test_invalid_configuration(qualifier, window):
    with pytest.raises(ValueError):
        rerank_window([], build_query_bundle(CONTROLS["question"]), window_size=window, qualifier=qualifier)


def test_scope_uses_original_question_only():
    assert in_scope(CONTROLS["question"])
    assert not in_scope("Nafion swelling")
