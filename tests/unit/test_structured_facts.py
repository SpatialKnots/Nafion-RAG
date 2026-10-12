from __future__ import annotations

import hashlib
import json
import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.db.models import Chunk
from app.facts.extraction import (
    RULE_BASED_NUMERIC_SOURCE,
    extract_structured_fact_candidates_from_chunk,
)


def test_extract_structured_fact_candidates_from_numeric_table_chunk() -> None:
    chunk = Chunk(
        id=uuid.uuid4(),
        article_id=uuid.uuid4(),
        source_type="table",
        text_layer="original",
        chunk_index=0,
        page_start=4,
        page_end=4,
        text="Table 2. Conductivity data\nEC/SL 25 °C 1.2e-3 S cm-1\nuptake 18 wt %",
        char_count=72,
    )

    candidates = extract_structured_fact_candidates_from_chunk(chunk)

    assert [(candidate.field_name, candidate.field_value_text, candidate.unit) for candidate in candidates] == [
        ("temperature", "25 °C", "°C"),
        ("conductivity", "1.2e-3 S cm-1", "S cm-1"),
        ("swelling_or_uptake", "18 wt %", "wt %"),
    ]
    assert candidates[1].field_value_numeric == Decimal("0.0012")
    assert candidates[1].source_chunk_id == chunk.id
    assert candidates[1].source == RULE_BASED_NUMERIC_SOURCE
    assert candidates[1].confidence == Decimal("0.80")


def test_extract_structured_fact_candidates_ignores_numbers_without_units() -> None:
    chunk = SimpleNamespace(
        id=uuid.uuid4(),
        article_id=uuid.uuid4(),
        source_type="main_text",
        text="The experiment used sample 12 and figure 3 without a measured unit.",
    )

    assert extract_structured_fact_candidates_from_chunk(chunk) == []  # type: ignore[arg-type]


@pytest.mark.parametrize(("text", "value", "unit"), [
    ("2 × 10 −4 S cm −1", "0.0002", "S cm-1"),
    ("2 × 10⁻⁴ S cm⁻¹", "0.0002", "S cm-1"),
    ("1.90∙10−4 S/cm", "0.000190", "S cm-1"),
    ("1,43·10−4 mS cm−1", "0.000143", "mS cm-1"),
    ("−40 ◦C", "-40", "°C"),
    ("80 ◦C", "80", "°C"),
    ("33 kJ mol −1", "33", "kJ mol-1"),
    ("1.2 g cm⁻³", "1.2", "g cm-3"),
    ("2\u00a0×\u00a010\u00a0−4 S cm−1", "0.0002", "S cm-1"),
    ("1.2e−3 S/cm", "0.0012", "S cm-1"),
])
def test_numeric_typography_preserves_exact_source(text: str, value: str, unit: str) -> None:
    chunk = Chunk(id=uuid.uuid4(), article_id=uuid.uuid4(), text=text, source_type="main_text")
    candidates = extract_structured_fact_candidates_from_chunk(chunk)
    assert len(candidates) == 1
    assert candidates[0].field_value_text == text
    assert candidates[0].field_value_numeric == Decimal(value)
    assert candidates[0].unit == unit
    assert candidates[0].source_chunk_id == chunk.id
    assert chunk.text == text


@pytest.mark.parametrize("text", [
    "2 × 10 − S cm−1", "2 × 10 ^−4 S cm−1", "2 × 10 - 4 S cm−12",
    "2 × 10⁻ S cm⁻¹", "2 × 10⁻⁴ S cm⁻¹²", "sample12 °C", "1.2.3 S/cm",
])
def test_malformed_numeric_tokens_do_not_yield_partial_facts(text: str) -> None:
    chunk = Chunk(id=uuid.uuid4(), article_id=uuid.uuid4(), text=text, source_type="main_text")
    assert extract_structured_fact_candidates_from_chunk(chunk) == []


def test_units_are_not_borrowed_across_lines_or_converted() -> None:
    chunk = Chunk(id=uuid.uuid4(), article_id=uuid.uuid4(), source_type="table",
                  text="S/cm\n1.90∙10−4\n1.2 mS/cm\n2 × 10−4\nS cm−1")
    candidates = extract_structured_fact_candidates_from_chunk(chunk)
    assert [(c.field_value_numeric, c.unit) for c in candidates] == [(Decimal("1.2"), "mS cm-1")]


def test_exponent_suffix_guard_does_not_reject_ordinary_prose() -> None:
    chunk = Chunk(id=uuid.uuid4(), article_id=uuid.uuid4(), source_type="main_text",
                  text="index 40 °C\nuptake 18 wt %\n2X10^−4 S/cm")
    candidates = extract_structured_fact_candidates_from_chunk(chunk)
    assert [c.field_value_text for c in candidates] == ["40 °C", "18 wt %"]


def test_typographic_additions_do_not_displace_existing_values_at_cap() -> None:
    chunk = Chunk(id=uuid.uuid4(), article_id=uuid.uuid4(), source_type="main_text",
                  text="80 ◦C\n" + "\n".join(f"{i} °C" for i in range(12)))
    candidates = extract_structured_fact_candidates_from_chunk(chunk)
    assert [c.field_value_numeric for c in candidates] == [Decimal(i) for i in range(12)]


def test_typographic_matches_fill_spare_slots_in_source_order() -> None:
    chunk = Chunk(id=uuid.uuid4(), article_id=uuid.uuid4(), source_type="main_text", text="80 ◦C\n25 °C")
    assert [c.field_value_numeric for c in extract_structured_fact_candidates_from_chunk(chunk)] == [Decimal(80), Decimal(25)]


def test_signed_additive_and_diameter_marker_remain_recognized() -> None:
    chunk = Chunk(id=uuid.uuid4(), article_id=uuid.uuid4(), source_type="main_text",
                  text="F3EME+1 wt% LiDFP\n15.95 mmϕ")
    assert [c.field_value_text for c in extract_structured_fact_candidates_from_chunk(chunk)] == ["+1 wt%", "15.95 mm"]


@pytest.mark.parametrize("text", [
    "~10 −9 S cm −1", "10-9 S/cm", "10 - 9 S/cm", "10\n−9 S/cm",
    "10⁻⁹ S/cm", "10^−9 S/cm",
    "212 ± 18 ◦C", "212 ±\n18 ◦C", "212 +/- 18 °C", "212 +/-18 °C", "212 ∓ 18 °C",
    "783 cm-1", "783 cm -1", "783 cm −1", "783 cm⁻¹", "783 cm ^ -1",
    "2 g / mol", "2 cm ²", "7–17%",
    "—16 ◦C", "— 16 ◦C", "–16 °C", "− 16 °C", "- 16 °C",
])
def test_unsupported_numeric_structures_do_not_become_scalars(text: str) -> None:
    chunk = Chunk(id=uuid.uuid4(), article_id=uuid.uuid4(), text=text, source_type="main_text")
    assert extract_structured_fact_candidates_from_chunk(chunk) == []


@pytest.mark.parametrize(("text", "value"), [
    ("-16 °C", "-16"), ("−16 ◦C", "-16"), ("+16 °C", "16"),
    ("2 × 10 −9 S cm −1", "2e-9"), ("2 × 10⁻⁹ S cm⁻¹", "2e-9"),
    ("783 cm", "783"), ("10 °C", "10"),
])
def test_numeric_guards_preserve_complete_supported_values(text: str, value: str) -> None:
    chunk = Chunk(id=uuid.uuid4(), article_id=uuid.uuid4(), text=text, source_type="main_text")
    candidates = extract_structured_fact_candidates_from_chunk(chunk)
    assert [(c.field_value_text, c.field_value_numeric) for c in candidates] == [(text, Decimal(value))]


def test_numeric_guards_keep_separate_rows_with_signed_measurements() -> None:
    chunk = Chunk(id=uuid.uuid4(), article_id=uuid.uuid4(), source_type="table",
                  text="25 °C\n-16 °C\n+20 °C")
    assert [c.field_value_text for c in extract_structured_fact_candidates_from_chunk(chunk)] == [
        "25 °C", "-16 °C", "+20 °C",
    ]


def test_previously_pdf_reviewed_blockers_are_absent_from_exact_fragments() -> None:
    labels = json.loads((Path(__file__).resolve().parents[2] / "docs/numeric_change_review.json").read_text(encoding="utf-8"))
    blockers = [label for label in labels["labels"] if label["verdict"] == "blocker"]
    assert {label["id"] for label in blockers} == {"bare_power", "uncertainty_operand", "inverse_unit", "dash_sign"}
    for label in blockers:
        assert hashlib.sha256(label["text"].encode()).hexdigest() == label["text_sha256"]
        chunk = Chunk(id=uuid.UUID(label["chunk_id"]), article_id=uuid.UUID(label["candidate"]["article_id"]),
                      text=label["text"], source_type="main_text")
        assert label["candidate"]["field_value_text"] not in [
            c.field_value_text for c in extract_structured_fact_candidates_from_chunk(chunk)
        ]


@pytest.mark.parametrize("text", [
    "30 \uf0b1 8 nm", "30\n\uf0b1 8 nm", "90 \uf0b1 25 nm",
    r"1659 cm\u00011", "1659 cm\x011",
    "8\u2009g\u2009Ah−1", "8 g Ah⁻¹", "2.4 g Ah–1", "8 mg mAh-1",
    "E/C = 2.4 g Ah−1. g,h, Long-cycling performance",
])
def test_reviewed_glyph_and_capacity_suffixes_are_not_scalars(text: str) -> None:
    chunk = Chunk(text=text)
    assert extract_structured_fact_candidates_from_chunk(chunk) == []
    assert chunk.text == text


def test_new_guards_preserve_supported_mass_length_and_conductivity() -> None:
    chunk = Chunk(text="8 g of salt\n8 mg additive\n8 nm\n0.013 S/cm")
    assert [c.field_value_text for c in extract_structured_fact_candidates_from_chunk(chunk)] == [
        "8 g", "8 mg", "8 nm", "0.013 S/cm",
    ]


def test_cap_review_false_additions_are_rejected_in_exact_source_fragments() -> None:
    labels = json.loads((Path(__file__).resolve().parents[2] / "docs/numeric_guard_change_review.json").read_text(encoding="utf-8"))
    targets = {"symbol_uncertainty", "escaped_inverse_unit", "compound_capacity_unit"}
    reviewed = [label for label in labels["labels"] if label["id"] in targets]
    assert {label["id"] for label in reviewed} == targets
    for label in reviewed:
        assert hashlib.sha256(label["text"].encode()).hexdigest() == label["text_sha256"]
        chunk = Chunk(text=label["text"])
        assert label["candidate"]["field_value_text"] not in [
            c.field_value_text for c in extract_structured_fact_candidates_from_chunk(chunk)
        ]


@pytest.mark.parametrize("text", [
    "(Fig. 2g-i)", "Fig. 5k", "Figure 5g", "Figs. 2a, 5g", "Figs. 2a and 5k",
    "рис. 5g", "Fig.\n2g", "10 mm min−1", r"10 mm min\u00011", "10 mm min\x011",
    "10 mm min⁻¹", "10 °C min-1", "10 mm s−1", "10 mm h⁻¹", "10 mm min−1. g,h, panels",
])
def test_reference_and_rate_tokens_are_not_scalar_measurements(text: str) -> None:
    assert extract_structured_fact_candidates_from_chunk(Chunk(text=text)) == []


def test_reference_guard_keeps_real_measurements_and_later_valid_occurrence() -> None:
    chunk = Chunk(text="Fig. 5g\nSample mass 5g; temperature 5K.\nFig. 2 shows 10 mm samples.\n10 mm minimum length.")
    assert [c.field_value_text for c in extract_structured_fact_candidates_from_chunk(chunk)] == ["5g", "5K", "10 mm"]


def test_reviewed_reference_and_rate_fragments_do_not_yield_false_candidates() -> None:
    labels = json.loads((Path(__file__).resolve().parents[2] / "docs/numeric_reference_cases.json").read_text(encoding="utf-8"))["labels"]
    assert {label["id"] for label in labels} == {"figure_mass", "figure_temperature", "deformation_rate"}
    for label in labels:
        assert hashlib.sha256(label["text"].encode()).hexdigest() == label["text_sha256"]
        assert label["candidate"]["field_value_text"] not in [
            c.field_value_text for c in extract_structured_fact_candidates_from_chunk(Chunk(text=label["text"]))
        ]
