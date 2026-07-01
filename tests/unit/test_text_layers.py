from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from app.ingestion.text_layers import OCR_LAYER, ORIGINAL_LAYER, choose_text_layer, score_text_layer


def _layer(layer_type: str, usable: bool, score: float) -> SimpleNamespace:
    return SimpleNamespace(layer_type=layer_type, has_usable_text=usable, quality_score=Decimal(str(score)))


def test_quality_score_rejects_noisy_ocr_text() -> None:
    usable, score = score_text_layer("Р Р Р В В \ufffd \ufffd !!!")

    assert not usable
    assert score < 0.5


def test_choose_text_layer_prefers_usable_original_over_similar_ocr() -> None:
    original = _layer(ORIGINAL_LAYER, True, 0.72)
    ocr = _layer(OCR_LAYER, True, 0.80)

    assert choose_text_layer(original, ocr).layer_type == ORIGINAL_LAYER  # type: ignore[arg-type, union-attr]


def test_choose_text_layer_uses_ocr_when_original_is_empty() -> None:
    original = _layer(ORIGINAL_LAYER, False, 0.05)
    ocr = _layer(OCR_LAYER, True, 0.70)

    assert choose_text_layer(original, ocr).layer_type == OCR_LAYER  # type: ignore[arg-type, union-attr]
