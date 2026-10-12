from decimal import Decimal

import pytest

from app.db.models import Chunk
from app.facts.extraction import diagnose_numeric_occurrences
from scripts.stage3_numeric_occurrence_audit import chunk_record


def test_rejected_range_does_not_claim_later_cap_omitted_occurrence() -> None:
    text = "423–523 K\r\n" + "\n".join(f"{i} K" for i in range(12)) + "\nat 523 K\n523 K"
    candidates, rows = diagnose_numeric_occurrences(Chunk(text=text))
    assert [c.field_value_numeric for c in candidates] == [Decimal(i) for i in range(12)]
    targets = [r for r in rows if r.text == "523 K"]
    assert [r.decision for r in targets] == ["rejected", "cap_omitted", "duplicate"]
    assert targets[0].reason == "uncertainty_or_dash_prefix"
    assert targets[2].duplicate_of_start == targets[1].start
    assert targets[1].start == text.index("523 K", text.index("at "))
    for row in rows:
        assert text[row.start:row.end] == row.text


@pytest.mark.parametrize(("text", "reason"), [
    ("Fig. 5g", "figure_reference"),
    ("± 5 K", "uncertainty_or_dash_prefix"),
    ("10 ^ 5 K", "bare_power_exponent"),
    ("5 cm / s", "powered_or_compound_unit"),
    (r"5 cm \u00011", "corrupt_inverse_suffix"),
    ("10 mm min⁻¹", "rate_suffix"),
    ("5 g Ah⁻¹", "capacity_denominator"),
    ("min -1 K", "denominator_exponent"),
    ("× 5 K", "scientific_number_suffix"),
])
def test_rejection_reasons(text: str, reason: str) -> None:
    candidates, rows = diagnose_numeric_occurrences(Chunk(text=text))
    assert candidates == []
    assert len(rows) == 1
    assert (rows[0].decision, rows[0].reason) == ("rejected", reason)


def test_typographic_priority_and_unmatched_scope() -> None:
    text = "25 ◦C\n" + "\n".join(f"{i} K" for i in range(12)) + "\n42 bananas"
    candidates, rows = diagnose_numeric_occurrences(Chunk(text=text))
    assert len(rows) == 13
    assert rows[0].decision == "cap_omitted"
    assert rows[0].legacy_slot is False
    assert [c.field_value_numeric for c in candidates] == [Decimal(i) for i in range(12)]


@pytest.mark.parametrize(("page_end", "page"), [(3, 3), (4, None)])
def test_report_preserves_provenance_without_guessing_page(page_end: int, page: int | None) -> None:
    chunk = Chunk(text="α\r\n5 K\n5 K", page_start=3, page_end=page_end, text_layer="ocr", source_type="table")
    record = chunk_record(chunk)
    assert record["occurrence_page"] == page
    assert record["page_start"] == 3 and record["page_end"] == page_end
    assert record["text_layer"] == "ocr" and record["source_type"] == "table"
    first, duplicate = record["occurrences"]
    assert first["start"] == 3 and first["source_line"] == "5 K"
    assert first["candidate"]["field_value_numeric"] == Decimal(5)
    assert duplicate["duplicate_of_start"] == first["start"]
    assert duplicate["candidate"] is None
