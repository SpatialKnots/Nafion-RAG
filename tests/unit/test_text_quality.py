from __future__ import annotations

from app.extraction.text_quality import has_usable_text_layer, should_run_ocr


def test_has_usable_text_layer_for_real_text() -> None:
    page = "Nafion membranes show ionic conductivity in hydrated lithium form. " * 3

    assert has_usable_text_layer([page])


def test_has_usable_text_layer_for_russian_text() -> None:
    page = "Мембраны Нафион показывают ионную проводимость в литиевой форме после гидратации. " * 3

    assert has_usable_text_layer([page])


def test_should_run_ocr_for_empty_or_poor_text() -> None:
    assert should_run_ocr(["", "   "], ocr_enabled=True)
    assert not should_run_ocr(["", "   "], ocr_enabled=False)
