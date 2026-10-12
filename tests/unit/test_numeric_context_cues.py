import json
from pathlib import Path

import pytest

from app.db.models import Chunk
from app.facts.extraction import diagnose_numeric_occurrences, extract_structured_fact_candidates_from_chunk


@pytest.mark.parametrize(("prefix", "kind"), [
    ("Scale bars, ", "scale_bar_cue"), ("масштабная линейка: ", "scale_bar_cue"),
    ("~", "approximation_cue"), ("≈ ", "approximation_cue"), ("roughly ", "approximation_cue"),
    ("примерно ", "approximation_cue"), ("ca. ", "approximation_cue"),
    ("≤", "inequality_cue"), (">= ", "inequality_cue"), ("at most ", "inequality_cue"),
    ("не менее ", "inequality_cue"),
])
def test_cues_preserve_source_spans(prefix: str, kind: str) -> None:
    text = "α\r\n" + prefix + "10 nm"
    chunk = Chunk(text=text)
    candidates, rows = diagnose_numeric_occurrences(chunk)
    assert candidates == extract_structured_fact_candidates_from_chunk(chunk)
    assert len(rows) == 1
    cue, = rows[0].context_cues
    assert cue.kind == kind
    assert text[cue.start:cue.end] == cue.text == prefix.strip().rstrip(",:").strip()


@pytest.mark.parametrize("text", [
    "Scale bars, 10 nm. Treatment at 25°C", "Scale bars, 10 nm\nTreatment at 25°C",
    "Approximately 10 nm, temperature 25°C", "≤2%, measured at 25°C",
    "Pristine 25°C 100°C 175°C 250°C", "Treatment Temperature\nPristine 25°C",
])
def test_cues_do_not_spread_to_another_number(text: str) -> None:
    _, rows = diagnose_numeric_occurrences(Chunk(text=text))
    row = next(r for r in rows if r.text == "25°C")
    assert row.context_cues == []


def test_duplicate_and_cap_omitted_occurrences_keep_their_own_cues() -> None:
    text = "\n".join(f"{i} K" for i in range(12)) + "\nYield: roughly 55%.\nAnother yield: roughly 55%."
    candidates, rows = diagnose_numeric_occurrences(Chunk(text=text))
    assert len(candidates) == 12
    targets = [r for r in rows if r.text == "55%"]
    assert [r.decision for r in targets] == ["cap_omitted", "duplicate"]
    assert targets[1].duplicate_of_start == targets[0].start
    assert [r.context_cues[0].kind for r in targets] == ["approximation_cue"] * 2
    assert targets[0].context_cues[0].start != targets[1].context_cues[0].start


def test_isolated_numeric_line_does_not_assign_a_scale_bar_role() -> None:
    _, rows = diagnose_numeric_occurrences(Chunk(text="10 nm\n10 nm"))
    assert [[c.kind for c in r.context_cues] for r in rows] == [["isolated_numeric_line"]] * 2


REVIEW = json.loads(Path("docs/numeric_occurrence_pdf_review.json").read_text(encoding="utf-8"))
SOURCE_CASES = [(r, i, o) for r in REVIEW["records"] for i, o in enumerate(r["occurrences"])]


@pytest.mark.parametrize(("record", "index", "source"), SOURCE_CASES)
def test_pdf_reviewed_lines_have_expected_cues(record: dict, index: int, source: dict) -> None:
    # Exact, previously PDF-reviewed stored lines; live provenance replay is separate.
    _, rows = diagnose_numeric_occurrences(Chunk(text=source["line"]))
    row = next(r for r in rows if r.text == record["target"][2])
    expected = []
    if record["index"] == 0:
        expected = ["isolated_numeric_line"]
    elif record["index"] == 7:
        expected = ["scale_bar_cue"]
    elif record["index"] == 10 or (record["index"] == 11 and index == 2) or (record["index"] == 12 and index == 1):
        expected = ["approximation_cue"]
    elif record["index"] == 13 and index == 1:
        expected = ["inequality_cue"]
    assert [c.kind for c in row.context_cues] == expected
    for cue in row.context_cues:
        assert source["line"][cue.start:cue.end] == cue.text
