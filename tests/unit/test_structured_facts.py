from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

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
