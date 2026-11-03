from scripts.complete_retrieval_window_review import source_delta


def test_displaced_unlabelled_article_and_changed_text_are_not_hidden_by_same_article_hit():
    before = [{"article_id": "a", "chunk_id": "1", "text": "old raw"}, {"article_id": "b", "chunk_id": "2", "text": "other raw"}]
    after = [{"article_id": "a", "chunk_id": "1", "text": "changed raw"}]
    delta = source_delta(before, after)
    assert delta["removed_raw_evidence"] == before
    assert delta["added_raw_evidence"] == after
    assert delta["removed_article_ids"] == ["b"]
    assert delta["added_article_ids"] == []


def test_reordering_does_not_claim_source_displacement():
    rows = [{"article_id": "a", "chunk_id": "1", "text": "one"}, {"article_id": "b", "chunk_id": "2", "text": "two"}]
    result = source_delta(rows, list(reversed(rows)))
    assert result["removed_raw_evidence"] == []
    assert result["added_raw_evidence"] == []
