"""Integrity/recognition checks; no generated answers or scientific gold scores."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.prepare_user_benchmark_intake import pre
from scripts.user_benchmark_intake import parse_document, quote_match, registered_pdf

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "docs/records/Nafion_RAG_Benchmark_v1.0_original.md"


def test_original_sections_and_question_offsets_are_verbatim():
    raw = ORIGINAL.read_bytes().decode("utf-8")
    cases = parse_document(raw)
    assert [c["id"] for c in cases] == ["Q01", "Q02", "Q03", "Q04", "Q05"]
    assert sum(len(c["quotes"]) for c in cases) == 14
    for case in cases:
        span = case["question_span"]
        assert raw[span["start"]:span["end"]] == span["text"] == case["question"]
        assert case["case_markdown_verbatim"] in raw
        assert case["reference_answer_markdown_verbatim"] in raw
        assert case["model_answer"] is None and case["scientific_score"] is None


@pytest.mark.parametrize("old,new", [("## Q03", "## Q02"), ("## Q05", "## Q06"), ("### Подтверждение", "### Нет раздела")])
def test_malformed_reference_rejected(old, new):
    with pytest.raises(ValueError):
        parse_document(ORIGINAL.read_text(encoding="utf-8").replace(old, new, 1))


def test_raw_exact_anchor():
    assert quote_match("prefix 0.15 M suffix", "0.15 M") == {
        "state": "raw_exact", "span": {"start": 7, "end": 13, "text": "0.15 M"}}


def test_mapped_anchor_preserves_original_ligature_and_break():
    raw = "prefix diﬂuoro\nborate 1.0 M suffix"
    result = quote_match(raw, "difluoro borate 1.0 M")
    assert result["state"] == "mapped_typographic_match"
    span = result["span"]
    assert raw[span["start"]:span["end"]] == span["text"] == "diﬂuoro\nborate 1.0 M"


@pytest.mark.parametrize("source,quote", [
    ("−65.0 J/g", "65.0 J/g"),
    ("1.0 mM", "1.0 M"),
    ("1.0 MM", "1.0 M"),
    ("0.228 S/cm", "0.028 S/cm"),
    ("did not change", "did change"),
    ("25 ◦C", "25 °C"),
    ("film-\nforming", "film-forming"),
])
def test_recognition_does_not_repair_known_mismatches(source, quote):
    # A substring quote without a sign would technically match; include the
    # quantity context so the sign cannot disappear across the requested text.
    assert quote_match("value " + source, "value " + quote)["state"] == "not_matched"


def test_unknown_pdf_rejected_before_file_read(tmp_path):
    with pytest.raises(ValueError, match="Unregistered"):
        registered_pdf(str(tmp_path / "missing.pdf"), [])


def test_later_whole_occurrence_is_used_after_truncated_prefix():
    raw = "1.0 MM; then 1.0 M"
    result = quote_match(raw, "1.0 M")
    assert result["state"] == "raw_exact"
    assert result["span"]["start"] == raw.rindex("1.0 M")


def test_registered_pdf_hash_drift_rejected(tmp_path):
    pdf = tmp_path / "fixture.pdf"
    pdf.write_bytes(b"original source")
    selection = [{"original_pdf_path": str(pdf), "original_pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest()}]
    assert registered_pdf(str(pdf), selection) == selection[0]
    pdf.write_bytes(b"changed source")
    with pytest.raises(ValueError, match="hash mismatch"):
        registered_pdf(str(pdf), selection)


def test_untrusted_document_markup_is_escaped():
    assert pre('<script>alert("x")</script>') == '<pre>&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;</pre>'
