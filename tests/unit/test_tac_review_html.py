from dataclasses import asdict
from pathlib import Path

import pytest

from scripts.tac_experiment import digest, span, title_from_layout, validate_profiles
from scripts.tac_review_html import render_table, visible_text


def fixture(tmp_path: Path):
    (tmp_path / "synthetic.pdf").write_bytes(b"synthetic path-only fixture, not a real PDF")
    raw = "A title <script>alert(1)</script>\nExact abstract\n"
    page = {"page": 1, "text": raw, "text_sha256": digest(raw.encode()), "layer": "original", "layer_id": "synthetic"}
    article = {
        "article_id": "synthetic",
        "original_pdf_path": "synthetic.pdf",
        "original_pdf_sha256": "a" * 64,
        "pages": [page],
        "chunks": [],
    }
    profile = {
        "article_id": "synthetic",
        "metadata_title": "Stored source name",
        "original_pdf_path": "synthetic.pdf",
        "original_pdf_sha256": "a" * 64,
        "sections": [asdict(span(page, "T", 0, raw.index("\n"), "synthetic"))],
        "diagnostics": ["unreviewed"],
        "layout_warnings": [],
    }
    snapshot = {"articles": [article], "created_at": "synthetic timestamp"}
    profiles = {"schema": "synthetic test version", "snapshot_sha256": "b" * 64, "profiles": [profile]}
    metadata = {"articles": [{"article_id": "synthetic", "checksum_sha256": "a" * 64, "authors": None, "journal": None, "year": None}]}
    return snapshot, profiles, metadata


def test_html_escapes_source_markup_and_keeps_missing_fields_visible(tmp_path: Path):
    snapshot, profiles, metadata = fixture(tmp_path)
    result = render_table(snapshot, profiles, metadata, tmp_path, "c" * 64)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in result
    assert "<script>alert(1)</script>" not in result
    assert result.count("<tr data-id=") == 1
    assert "Извлечение Terms не реализовано" in result
    assert "Не заполнено" in result and "Не распознано текущим TAC" in result
    assert (tmp_path / "synthetic.pdf").as_uri() in result
    assert "synthetic test version" in result and "b" * 64 in result and "c" * 64 in result


def test_html_metadata_mismatch_or_missing_pdf_fails(tmp_path: Path):
    snapshot, profiles, metadata = fixture(tmp_path)
    metadata["articles"][0]["checksum_sha256"] = "d" * 64
    with pytest.raises(ValueError, match="checksum"):
        render_table(snapshot, profiles, metadata, tmp_path, "c" * 64)
    metadata["articles"][0]["checksum_sha256"] = "a" * 64
    (tmp_path / "synthetic.pdf").unlink()
    with pytest.raises(FileNotFoundError):
        render_table(snapshot, profiles, metadata, tmp_path, "c" * 64)


def test_profile_validation_rejects_wrong_layer_and_duplicate_article(tmp_path: Path):
    snapshot, profiles, _metadata = fixture(tmp_path)
    validate_profiles(snapshot, profiles, "b" * 64)
    profiles["profiles"][0]["sections"][0]["layer_id"] = "wrong"
    with pytest.raises(ValueError, match="evidence"):
        validate_profiles(snapshot, profiles, "b" * 64)
    profiles["profiles"][0]["sections"][0]["layer_id"] = "synthetic"
    profiles["profiles"].append(profiles["profiles"][0])
    with pytest.raises(ValueError, match="inventory"):
        validate_profiles(snapshot, profiles, "b" * 64)


def test_controls_are_visible_without_changing_valid_unicode():
    assert visible_text("Li-Naﬁon 😀\n\x01") == "Li-Naﬁon 😀\n⟦U+0001⟧"


def test_html_marks_changes_and_preserves_previous_source_text(tmp_path: Path):
    from copy import deepcopy

    snapshot, profiles, metadata = fixture(tmp_path)
    previous = deepcopy(profiles)
    previous["profiles"][0]["sections"] = []
    result = render_table(snapshot, profiles, metadata, tmp_path, "c" * 64, previous_profiles=previous)
    assert '<span class="change">Изменено</span>' in result and "Прежнее T" in result
    previous["snapshot_sha256"] = "wrong"
    with pytest.raises(ValueError, match="snapshot"):
        render_table(snapshot, profiles, metadata, tmp_path, "c" * 64, previous_profiles=previous)


def test_conference_abstract_status_does_not_claim_missing_body_text(tmp_path: Path):
    snapshot, profiles, metadata = fixture(tmp_path)
    profiles["profiles"][0]["section_status"] = {"A": "not_separately_delimited"}
    result = render_table(snapshot, profiles, metadata, tmp_path, "c" * 64)
    assert "Конференционный abstract: отдельная A не выделена" in result


def test_summary_passages_are_labelled_and_role_mismatch_is_rejected(tmp_path: Path):
    snapshot, profiles, metadata = fixture(tmp_path)
    profile = profiles['profiles'][0]
    section = dict(profile['sections'][0], kind='C', method='proposed_implicit_summary_passage')
    profile['sections'].append(section)
    profile['conclusion_kind'] = 'summary_passages'
    validate_profiles(snapshot, profiles, 'b' * 64)
    result = render_table(snapshot, profiles, metadata, tmp_path, 'c' * 64)
    assert 'Итоговые фрагменты; отдельный раздел Conclusions не найден' in result
    section['method'] = 'explicit_heading_text_order'
    with pytest.raises(ValueError, match='conclusion kind'):
        validate_profiles(snapshot, profiles, 'b' * 64)


def test_title_merges_pdf_blocks_and_ignores_large_body_formula(tmp_path: Path):
    import fitz

    pdf = tmp_path / "synthetic_layout.pdf"
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((50, 85), "First scientific paper title", fontsize=17)
        page.insert_text((75, 115), "continued across another block", fontsize=17)
        page.insert_text((50, 155), "ABSTRACT: A short summary.", fontsize=10)
        page.insert_text((50, 220), "H2O Li2O Example formula block", fontsize=30)
        document.save(pdf)
        text = page.get_text("text")
    source = {
        "page": 1,
        "text": text,
        "text_sha256": digest(text.encode()),
        "layer": "original",
        "layer_id": "synthetic",
        "layer_pdf_path": str(pdf),
    }
    title, _ = title_from_layout(source)
    assert title is not None
    assert title.quote.strip() == "First scientific paper title\ncontinued across another block"
    assert text[title.start : title.end] == title.quote
