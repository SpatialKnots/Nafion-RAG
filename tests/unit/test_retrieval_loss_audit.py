"""Evidence-loss diagnostics must distinguish source text, page overlap and branched paths."""

import pytest

from scripts.retrieval_loss_audit import anchor_presence, retention_path


def row(**updates):
    return {"article_id": "article-a", "chunk_id": "chunk-a", "page_start": 74, "page_end": 75,
            "text_layer": "original", "full_text": "before exact source fragment after", **updates}


TARGET = {"article_id": "article-a", "page_number": 75, "exact_text": "exact source fragment"}


@pytest.mark.parametrize("change", [
    {"article_id": "article-b"}, {"page_end": 74}, {"page_start": 76, "page_end": 77},
    {"full_text": None, "snippet": "exact source fragment"},
    {"full_text": "other text", "title": "exact source fragment"},
    {"full_text": "exact source\nfragment"},
])
def test_wrong_work_page_snippet_title_and_normalized_text_are_not_exact_evidence(change):
    assert not anchor_presence([row(**change)], **TARGET)["anchor_present"]


def test_page_overlap_without_anchor_is_preserved_as_diagnostic():
    result = anchor_presence([row(full_text="only preceding page text")], **TARGET)
    assert len(result["page_range_matches"]) == 1
    assert result["exact_anchor_matches"] == []
    assert not result["anchor_present"]


def test_all_overlapping_chunks_and_ranks_remain_visible():
    result = anchor_presence([row(chunk_id="unrelated", article_id="b"), row(), row(chunk_id="chunk-b")], **TARGET)
    assert [(r["chunk_id"], r["rank"]) for r in result["exact_anchor_matches"]] == [("chunk-a", 2), ("chunk-b", 3)]


def test_generation_evidence_text_is_checked_without_assuming_text_layer():
    evidence = row()
    evidence["text"] = evidence.pop("full_text")
    evidence.pop("text_layer")
    result = anchor_presence([evidence], **TARGET)
    assert result["anchor_present"]
    assert result["exact_anchor_matches"][0]["text_layer"] == "unknown"


def test_explicit_path_records_loss_and_reentry_without_claiming_final_absence_is_initial_loss():
    result = retention_path([
        {"name": "candidate", "results": [row()]},
        {"name": "window", "results": []},
        {"name": "restored", "results": [row()]},
        {"name": "top_k", "results": [row()]},
    ], **TARGET)
    assert [s["transition"] for s in result] == ["initial", "lost", "entered", "retained"]


def test_absent_from_both_stages_does_not_invent_a_loss():
    result = retention_path([{"name": "a", "results": []}, {"name": "b", "results": []}], **TARGET)
    assert [s["transition"] for s in result] == ["initial", "retained"]


def test_duplicate_stage_names_are_rejected():
    with pytest.raises(ValueError, match="unique"):
        retention_path([{"name": "a", "results": []}, {"name": "a", "results": []}], **TARGET)


@pytest.mark.parametrize("change", [{"exact_text": ""}, {"exact_text": " \n"}, {"page_number": 0}])
def test_invalid_anchor_is_rejected(change):
    with pytest.raises(ValueError, match="anchor"):
        anchor_presence([], **(TARGET | change))
