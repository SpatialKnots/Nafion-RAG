from __future__ import annotations

from app.extraction.text_quality import (
    detect_caption_lines,
    detect_formula_like_lines,
    has_usable_text_layer,
    should_run_ocr,
    table_like_line_count,
    text_quality_signals,
)


def test_has_usable_text_layer_for_real_text() -> None:
    page = "Nafion membranes show ionic conductivity in hydrated lithium form. " * 3

    assert has_usable_text_layer([page])


def test_has_usable_text_layer_for_russian_text() -> None:
    page = "Мембраны Нафион показывают ионную проводимость в литиевой форме после гидратации. " * 3

    assert has_usable_text_layer([page])


def test_should_run_ocr_for_empty_or_poor_text() -> None:
    assert should_run_ocr(["", "   "], ocr_enabled=True)
    assert not should_run_ocr(["", "   "], ocr_enabled=False)


def test_detect_caption_lines_for_english_and_russian() -> None:
    text = (
        "Table 1. Conductivity values\n"
        "Fig. 2. Membrane image\n"
        "\u0422\u0430\u0431\u043b\u0438\u0446\u0430 3. \u0414\u0430\u043d\u043d\u044b\u0435\n"
    )

    captions = detect_caption_lines(text)

    assert len(captions) == 3
    assert captions[0].startswith("Table 1")


def test_table_like_line_count_detects_numeric_columns() -> None:
    text = "sample    conductivity    uptake\nA    12.3    45.0    6.7\nB    13.0    48.0    7.1\n"

    assert table_like_line_count(text) >= 2


def test_formula_like_lines_are_reported_without_symbolic_parsing() -> None:
    lines = detect_formula_like_lines("IEC = nSO3H / m\nplain text\nlambda = 14\n")

    assert lines == ["IEC = nSO3H / m", "lambda = 14"]


def test_text_quality_signals_count_control_and_artifacts() -> None:
    signals = text_quality_signals("Nafion\ufffd data\n-----\n-----\nword word word word\n")

    assert signals.control_char_ratio > 0
    assert signals.repeated_artifact_count >= 1
