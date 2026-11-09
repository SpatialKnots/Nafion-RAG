from __future__ import annotations

from copy import deepcopy

import pytest

from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import BASE, read
from scripts.benchmark_retrieval_replay_20261105 import replay as replay_historical_channels
from scripts.reference_quote_runtime_checks_20261105 import baseline_scope
from scripts.review_benchmark_retrieval_repair_20261105 import presence, render


def replay(*args, **kwargs):
    # This fixture predates reference lookup/quotation contracts. Keep validating
    # its exact historical boundaries; the new branch has separate service tests.
    with baseline_scope():
        return replay_historical_channels(*args, **kwargs)


@pytest.fixture(scope="module")
def source():
    return read(BASE / "capture_v02/Q01/boundaries.json")


@pytest.fixture(scope="module")
def settings():
    return files.configure()


def test_real_service_reproduces_every_baseline_boundary(source, settings):
    result = replay(source, settings)
    assert result["trace"] == source["trace"]
    assert len(result["stages"]) == len(source["stages"])
    assert result["boundary"] == source["boundary"]
    assert {c["name"] for c in result["channel_calls"]} == {"exact_search", "semantic_search"}


def test_corrupt_expected_trace_rejected(source, settings):
    broken = deepcopy(source)
    broken["trace"]["evidence"][0]["text"] += " unsupported alteration"
    with pytest.raises(ValueError, match="Baseline full service trace differs"):
        replay(broken, settings)


def test_corrupt_expected_ranking_boundary_rejected(source, settings):
    broken = deepcopy(source)
    stage = next(s for s in broken["stages"] if s["name"] == "_diversify_cross_lingual_results:1:output")
    stage["results"].reverse()
    with pytest.raises(ValueError, match="Boundary differs"):
        replay(broken, settings)


def test_corrupt_channel_source_rejected(source, settings):
    broken = deepcopy(source)
    stage = next(s for s in broken["stages"] if s["name"] == "exact_search:1:output")
    stage["results"][0]["full_text"] += " altered source"
    with pytest.raises(ValueError, match="differs"):
        replay(broken, settings)


def test_missing_channel_fails_instead_of_searching(source, settings):
    broken = deepcopy(source)
    broken["stages"] = [s for s in broken["stages"] if s["name"] != "semantic_search:1:output"]
    with pytest.raises(ValueError, match="Missing/ambiguous frozen channel"):
        replay(broken, settings)


def test_wide_rerank_does_not_change_channel_queries_or_top_k(source, settings):
    baseline = replay(source, settings)
    wide = replay(source, settings, wide=True)
    assert baseline["channel_calls"] == wide["channel_calls"]
    assert len(wide["trace"]["retrieval"]["results"]) <= source["api"]["top_k"]


def test_page_overlap_alone_does_not_count_as_quote():
    quote = {"pdf_page": 2, "span": {"start": 0, "end": 6, "text": "result"}}
    rows = [{"article_id": "a", "chunk_id": "x", "page_start": 1, "page_end": 2, "text": "unrelated"},
            {"article_id": "other", "chunk_id": "y", "page_start": 2, "page_end": 2, "text": "result"}]
    result = presence(rows, "a", [2], [quote])
    assert result["reference_pages_present"] == [2]
    assert result["mapped_quotes_retained"] == 0
    assert not result["meaning_or_ownership_validated"]


def test_raw_vs_whitespace_quote_match_distinguished():
    quote = {"pdf_page": 2, "span": {"start": 0, "end": 12, "text": "first\nsecond"}}
    rows = [{"article_id": "a", "chunk_id": "x", "page_start": 2, "page_end": 2, "text": "first second"}]
    result = presence(rows, "a", [2], [quote])
    assert result["mapped_quotes_retained"] == 1
    assert result["anchors"][0]["matches"] == [{"chunk_id": "x", "raw_exact": False, "raw_start": None}]


def test_report_escapes_untrusted_source_text():
    report = {"summary": {"v": "<script>unsafe</script>"}, "cases": [], "regressions": [], "articles": {}}
    html = render(report)
    assert "<script>unsafe</script>" not in html
    assert "&lt;script&gt;unsafe&lt;/script&gt;" in html
