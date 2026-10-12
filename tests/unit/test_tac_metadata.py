from copy import deepcopy
from pathlib import Path

import pytest

from scripts.tac_experiment import add_layout_blocks, digest, span
from scripts.tac_metadata import (
    VERSION,
    candidate,
    choose,
    evidence,
    extract_article,
    extract_authors,
    extract_bibliography,
    normalized_view,
    parse_names,
    validate_metadata,
)
from scripts.tac_review_html import metadata_cell


def page(text, y=40):
    return {
        "page": 1,
        "text": text,
        "text_sha256": digest(text.encode()),
        "layer": "original",
        "layer_id": "synthetic",
        "layout_warnings": [],
        "height": 800,
        "layout_blocks": [{"start": 0, "end": len(text), "bbox": (30, y, 500, y + 20)}],
    }


@pytest.mark.parametrize("name", ["Qirui He", "Jun Ho Lee", "Chia-Hung Ma", "M. Ue", "U-Ser Jeng", "Takayuki Doi"])
def test_names_preserve_short_surnames_hyphens_and_doi_surname(name):
    assert parse_names(name) == [name]


def test_names_parse_initials_markers_and_suffix_without_inferred_correction():
    assert parse_names("Elizaveta Yu. Evshchik a, and Yukio SASAKIa") == ["Elizaveta Yu. Evshchik", "Yukio SASAKI"]
    assert parse_names("R. B. Moore, 111, and C. R. Martin*") == ["R. B. Moore, 111", "C. R. Martin"]


@pytest.mark.parametrize("raw", ["C H", "Department of Chemistry", "Read Online", "J¸rgen O. Besenhard"])
def test_non_byline_or_corrupt_names_abstain(raw):
    # Chemical formula / publisher UI / damaged text is not silently repaired into a person.
    assert parse_names(raw) is None


def test_figure_labels_in_other_column_are_not_byline_candidates(tmp_path):
    source = pdf_page(
        tmp_path,
        [
            (40, 80, "An experimental scientific paper title", 17),
            (350, 120, "EME FEME", 11),
            (40, 180, "An ordinary body paragraph begins here.", 10),
        ],
    )
    title = span(source, "T", 0, source["text"].index("EME"), "synthetic")
    assert extract_authors(source, [title.__dict__]) == []


def test_normalized_view_retains_unicode_source_offsets():
    raw = "😀\n Nature\tEnergy   2025"
    text, offsets = normalized_view(raw)
    start, end = text.index("Nature"), text.index("2025") + 4
    assert raw[offsets[start] : offsets[end - 1] + 1] == "Nature\tEnergy   2025"


def test_issue_year_wins_over_online_date_and_keeps_both_sources():
    source = page("Example Journal 2026, 38, 1–7\nPublished on 21 December 2025\n")
    result = choose("year", extract_bibliography(source))
    assert result["value"] == 2026
    assert {c["value"] for c in result["candidates"]} == {2025, 2026}
    assert result["diagnostics"]


def test_reference_received_download_and_template_years_not_accepted():
    assert extract_bibliography(page("Example Journal 2024, 12, 21–29\n", y=400)) == []
    assert extract_bibliography(page("Received 2023\nAccepted 2024\nDownloaded in 2025\nJ. Name., 2013, 00, 1-3\n")) == []


def test_equal_priority_conflicting_years_are_not_silently_selected():
    source = page("Exact source")
    e = evidence(source, 0, len(source["text"]), "synthetic")
    result = choose("year", [candidate("year", y, 100, e, "synthetic") for y in (2024, 2025)])
    assert result["value"] is None and result["status"] == "ambiguous"
    assert len(result["candidates"]) == 2


def pdf_page(tmp_path: Path, entries):
    import fitz

    file = tmp_path / "synthetic_metadata.pdf"
    with fitz.open() as document:
        p = document.new_page()
        for x, y, text, font in entries:
            p.insert_text((x, y), text, fontsize=font)
        text = p.get_text("text")
        document.save(file)
    result = page(text)
    result["layer_pdf_path"] = str(file)
    return add_layout_blocks(result)


def test_fragmented_author_name_list_is_complete_and_keeps_exact_evidence(tmp_path):
    source = pdf_page(
        tmp_path,
        [
            (40, 80, "An experimental scientific paper title", 17),
            (40, 115, "Alice Smith, Bob Jones, Carol M.", 11),
            (40, 133, "Brown and David Lee", 11),
            (40, 155, "Department of Chemistry", 9),
            (40, 200, "ABSTRACT: Detailed scientific description.", 10),
        ],
    )
    title = span(source, "T", 0, source["text"].index("Alice"), "synthetic")
    result = choose("authors", extract_authors(source, [title.__dict__]))
    assert result["value"] == ["Alice Smith", "Bob Jones", "Carol M. Brown", "David Lee"]
    e = result["selected"][0]["evidence"]
    assert source["text"][e["start"] : e["end"]] == e["quote"]
    assert "Department" not in e["quote"]


def test_small_caps_surname_is_preserved_while_small_affiliation_is_removed(tmp_path):
    source = pdf_page(
        tmp_path,
        [
            (40, 80, "An experimental scientific paper title", 17),
            (40, 115, "Yukio", 12),
            (75, 115, "SASAKI", 9.5),
            (110, 110, "a", 7),
            (40, 150, "Department of Chemistry", 9),
        ],
    )
    title = span(source, "T", 0, source["text"].index("Yukio"), "synthetic")
    result = choose("authors", extract_authors(source, [title.__dict__]))
    assert result["value"] == ["Yukio SASAKI"]


def metadata_fixture():
    p = page("Alice Smith\nExample Journal 2024, 12, 1–7\n")
    article = {"article_id": "synthetic", "original_pdf_sha256": "a" * 64, "pages": [p]}
    e = evidence(p, 0, len(p["text"]), "synthetic")
    fields = {
        f: choose(f, [candidate(f, v, 100, e, "synthetic")])
        for f, v in [("authors", ["Alice Smith"]), ("journal", "Example Journal"), ("year", 2024)]
    }
    item = {"article_id": "synthetic", "checksum_sha256": "a" * 64, "fields": fields, **{f: r["value"] for f, r in fields.items()}}
    metadata = {"schema": VERSION, "snapshot_sha256": "b" * 64, "articles": [item]}
    return {"articles": [article]}, metadata


@pytest.mark.parametrize("key,value", [("quote", "wrong"), ("layer", "wrong"), ("start", -1), ("page_text_sha256", "wrong")])
def test_metadata_validation_rejects_source_tampering(key, value):
    snapshot, metadata = metadata_fixture()
    validate_metadata(snapshot, metadata, "b" * 64)
    metadata["articles"][0]["fields"]["year"]["candidates"][0]["evidence"][key] = value
    with pytest.raises(ValueError, match="evidence"):
        validate_metadata(snapshot, metadata, "b" * 64)


def test_metadata_validation_rejects_inventory_and_unsupported_value():
    snapshot, metadata = metadata_fixture()
    wrong = deepcopy(metadata)
    wrong["articles"].append(wrong["articles"][0])
    with pytest.raises(ValueError, match="inventory"):
        validate_metadata(snapshot, wrong, "b" * 64)
    metadata["articles"][0]["fields"]["year"]["value"] = "2024"
    with pytest.raises(ValueError, match="type"):
        validate_metadata(snapshot, metadata, "b" * 64)


def test_html_metadata_cells_show_full_names_source_quote_and_escape_markup():
    snapshot, metadata = metadata_fixture()
    item = metadata["articles"][0]
    item["authors"].append("<script>unsafe</script>")
    result = metadata_cell("authors", item, "file:///synthetic.pdf")
    assert "&lt;script&gt;unsafe&lt;/script&gt;" in result and "<script>unsafe</script>" not in result
    assert 'class="metadata-value"' in result and "#page=1" in result
    assert snapshot["articles"][0]["pages"][0]["text"] in result


def test_thesis_year_comes_from_title_page_and_journal_is_not_applicable(monkeypatch):
    import scripts.tac_metadata as module

    source = page("ИВАНОВ ИВАН ИВАНОВИЧ\nTitle\nДиссертация на соискание степени\nЕкатеринбург – 2026\n")
    monkeypatch.setattr(module, "add_layout_blocks", lambda p: p)
    monkeypatch.setattr(module, "extract_authors", lambda p, t: [])
    article = {"article_id": "synthetic", "original_pdf_sha256": "a" * 64, "pages": [source]}
    result = extract_article(article, {"sections": [{"kind": "T", "page": 1, "start": source["text"].index("Title")}]})
    assert result["authors"] == ["ИВАНОВ ИВАН ИВАНОВИЧ"]
    assert result["year"] == 2026 and result["journal"] is None
    assert result["fields"]["journal"]["status"] == "not_applicable"
