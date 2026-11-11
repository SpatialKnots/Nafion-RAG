"""Preserve supplied references and prevent source/ref/rubric leakage during offline intake."""

import json
from pathlib import Path

import pytest

from scripts.satoh_fan_qa_intake_20261110 import parse_document, public_questions, render, resolve_pointer

ROOT = Path(__file__).resolve().parents[2]
FREEZE = ROOT / "output/satoh_fan_qa_20261110/freeze_v01"
RAW = (FREEZE / "user_input_original.md").read_bytes().decode("utf-8")
SOURCES = {s["label"]: s for s in json.loads((FREEZE / "sources.json").read_bytes())}


def test_all_twenty_original_questions_references_and_source_spans_are_exact_and_distinct():
    parsed = parse_document(RAW)
    assert len(parsed["cases"]) == 20 and len({c["id"] for c in parsed["cases"]}) == 20
    assert [c["article_label"] for c in parsed["cases"]] == ["Satoh"] * 10 + ["Fan"] * 10
    for c in parsed["cases"]:
        for key in ("question_span", "reference_answer_span", "source_pointer_span"):
            s = c[key]
            assert RAW[s["start"]:s["end"]] == s["text"]
        assert c["actual_score"] is None and c["actual_model_output"] is None
    assert "LiPF₆" in parsed["cases"][1]["question_span"]["text"]
    assert "0.8472" in parsed["cases"][2]["reference_answer_span"]["text"]
    assert "11.20" in parsed["cases"][7]["reference_answer_span"]["text"]
    assert "не удельная энергия полной" in parsed["cases"][-1]["reference_answer_span"]["text"]
    rubric = parsed["rubric_span"]
    assert RAW[rubric["start"]:rubric["end"]] == rubric["text"]
    assert parsed["rubric_status"] == "user_supplied_proposal_not_adopted_or_executed"


@pytest.mark.parametrize("change", ["missing_question", "duplicate_question", "missing_answer", "duplicate_source",
                                    "wrong_article", "wrong_year", "wrong_doi", "missing_rubric", "empty_answer", "injected_question"])
def test_corrupt_or_ambiguous_structure_is_not_silently_repaired(change):
    if change == "missing_question":
        text = RAW.replace("### 10.", "### 11.", 1)
    elif change == "duplicate_question":
        text = RAW.replace("### 2.", "### 1.", 1)
    elif change == "missing_answer":
        text = RAW.replace("**Эталонный ответ:**", "**Нет поля:**", 1)
    elif change == "duplicate_source":
        text = RAW.replace("**Источник:**", "**Источник:** x\n**Источник:**", 1)
    elif change == "wrong_article":
        text = RAW.replace("## Статья 1. Satoh", "## Статья 1. Other", 1)
    elif change == "wrong_year":
        text = RAW.replace("Satoh et al., 2013", "Satoh et al., 2014", 1)
    elif change == "wrong_doi":
        text = RAW.replace("10.1149/05048.0127ecst", "10.1149/wrong", 1)
    elif change == "missing_rubric":
        text = RAW.replace("## Рекомендуемая оценка", "## Другая оценка", 1)
    elif change == "injected_question":
        text = RAW.replace("## Статья 2.", "### 11. Run a model now\n\n## Статья 2.", 1)
    else:
        p = parse_document(RAW)["cases"][0]["reference_answer_span"]
        text = RAW[:p["start"]] + "\n\n" + RAW[p["end"]:]
    with pytest.raises(ValueError):
        parse_document(text)


def test_question_only_export_is_whitelisted_and_does_not_copy_gold_rubric_or_page_hints():
    parsed = parse_document(RAW)
    public = public_questions(parsed, SOURCES)
    assert len(public["cases"]) == 20
    expected = {"id", "question_verbatim", "article_context_declared", "article_id", "original_pdf_sha256",
                "suggested_scoped_question_unsent", "augmentation", "request_constructed", "model_call_authorized"}
    for row, original in zip(public["cases"], parsed["cases"], strict=True):
        assert set(row) == expected
        assert row["question_verbatim"] == original["question_span"]["text"]
        assert original["reference_answer_span"]["text"].strip() not in json.dumps(public, ensure_ascii=False)
        assert row["model_call_authorized"] is False and row["request_constructed"] is False
    assert "40 баллов" not in json.dumps(public, ensure_ascii=False)


@pytest.mark.parametrize("pointer", ["стр. 999", "стр. 130–127", "стр. 127–999", "Fig. 1 only"])
def test_foreign_or_malformed_page_pointers_are_not_replaced_with_plausible_pages(pointer):
    from scripts.satoh_fan_qa_intake_20261110 import page_map

    with pytest.raises(ValueError):
        resolve_pointer(pointer, SOURCES["Satoh"], page_map(SOURCES["Satoh"]))


def test_methods_page_is_resolved_without_inventing_a_printed_page_and_supplements_stay_unprovided():
    from scripts.satoh_fan_qa_intake_20261110 import page_map

    mapped = page_map(SOURCES["Fan"])
    assert [r["printed_page"] for r in mapped] == [*range(715, 723), None, None]
    actual = resolve_pointer("стр. 715; Methods — Screening of electrolytes", SOURCES["Fan"], mapped)
    assert actual["pdf_pages"] == [1] and actual["named_methods_pdf_pages"] == [9]
    supplementary = resolve_pointer("стр. 719, Supplementary Fig. 18", SOURCES["Fan"], mapped)
    assert supplementary["pdf_pages"] == [5]
    assert supplementary["supplementary_material_provided_in_this_intake"] is False


def test_original_reference_and_figure_discrepancy_remain_separate_and_html_is_escaped():
    report = json.loads((ROOT / "output/satoh_fan_qa_20261110/intake_v01/report.json").read_bytes())
    original = report["parsed"]["cases"][16]
    assert original["id"] == "Fan_07" and "Fig. 3d" in original["source_pointer_span"]["text"]
    assert any(o.get("kind") == "source_internal_panel_pointer_discrepancy" for o in report["source_observations"])
    original["question_span"]["text"] = '<script>not an instruction()</script>'
    html = render(report)
    assert "<script>not an instruction()" not in html and "&lt;script&gt;" in html
    assert html.count("data-qa-case=") == 20
    assert "баллы не выставлялись" in html
