from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Article, PageTextLayer
from app.extraction.text_quality import MIN_ALNUM_RATIO, MIN_TEXT_CHARS_PER_PAGE, normalize_pdf_text
from app.ingestion.pdf_extract import ExtractedPage

ORIGINAL_LAYER = "original"
OCR_LAYER = "ocr"
QUALITY_SWITCH_MARGIN = 0.20


@dataclass(frozen=True)
class TextLayerInput:
    page_number: int
    layer_type: str
    text: str
    source_pdf_path: str
    has_usable_text: bool
    quality_score: float


@dataclass(frozen=True)
class SelectedPageText:
    page_number: int
    text: str
    selected_text_layer: str
    has_text_layer: bool
    ocr_used: bool


def score_text_layer(text: str) -> tuple[bool, float]:
    normalized = normalize_pdf_text(text)
    if not normalized:
        return False, 0.0

    length_score = min(len(normalized) / max(MIN_TEXT_CHARS_PER_PAGE * 4, 1), 1.0)
    alnum_count = sum(char.isalnum() for char in normalized)
    alpha_count = sum(char.isalpha() for char in normalized)
    printable_count = sum(char.isprintable() for char in normalized)
    alnum_ratio = alnum_count / max(len(normalized), 1)
    alpha_ratio = alpha_count / max(len(normalized), 1)
    printable_ratio = printable_count / max(len(normalized), 1)
    replacement_penalty = normalized.count("\ufffd") / max(len(normalized), 1)
    mojibake_penalty = len(re.findall(r"[РС][\x80-\xBF]|В[^\sA-Za-zА-Яа-я]", normalized)) / max(len(normalized), 1)

    has_usable_text = len(normalized) >= MIN_TEXT_CHARS_PER_PAGE and alnum_ratio >= MIN_ALNUM_RATIO
    score = (
        0.35 * length_score
        + 0.30 * min(alnum_ratio / 0.55, 1.0)
        + 0.25 * min(alpha_ratio / 0.45, 1.0)
        + 0.10 * printable_ratio
        - 2.0 * replacement_penalty
        - 4.0 * mojibake_penalty
    )
    return has_usable_text, max(0.0, min(1.0, score))


def build_layer_inputs(pages: list[ExtractedPage], *, layer_type: str, source_pdf_path: Path) -> list[TextLayerInput]:
    layers: list[TextLayerInput] = []
    for page in pages:
        has_usable_text, quality_score = score_text_layer(page.text)
        layers.append(
            TextLayerInput(
                page_number=page.page_number,
                layer_type=layer_type,
                text=page.text,
                source_pdf_path=str(source_pdf_path),
                has_usable_text=has_usable_text,
                quality_score=quality_score,
            )
        )
    return layers


def replace_text_layers(session: Session, article: Article, layers: list[TextLayerInput]) -> None:
    layer_types = {layer.layer_type for layer in layers}
    if not layer_types:
        return
    session.execute(delete(PageTextLayer).where(PageTextLayer.article_id == article.id).where(PageTextLayer.layer_type.in_(layer_types)))
    session.flush()
    for layer in layers:
        session.add(
            PageTextLayer(
                article_id=article.id,
                page_number=layer.page_number,
                layer_type=layer.layer_type,
                text=layer.text,
                has_usable_text=layer.has_usable_text,
                quality_score=layer.quality_score,
                source_pdf_path=layer.source_pdf_path,
            )
        )


def _float_score(layer: PageTextLayer | None) -> float:
    if layer is None:
        return 0.0
    score = layer.quality_score
    if isinstance(score, Decimal):
        return float(score)
    return float(score or 0.0)


def choose_text_layer(original: PageTextLayer | None, ocr: PageTextLayer | None) -> PageTextLayer | None:
    chosen = original or ocr
    if original is not None and original.has_usable_text:
        if ocr is not None and ocr.has_usable_text and _float_score(ocr) > _float_score(original) + QUALITY_SWITCH_MARGIN:
            return ocr
        return original
    if ocr is not None and ocr.has_usable_text:
        return ocr
    if original is not None and ocr is not None:
        return ocr if _float_score(ocr) > _float_score(original) else original
    return chosen


def select_best_pages(session: Session, article: Article) -> list[SelectedPageText]:
    rows = list(session.scalars(select(PageTextLayer).where(PageTextLayer.article_id == article.id).order_by(PageTextLayer.page_number)))
    by_page: dict[int, dict[str, PageTextLayer]] = {}
    for row in rows:
        by_page.setdefault(row.page_number, {})[row.layer_type] = row

    selected: list[SelectedPageText] = []
    for page_number in sorted(by_page):
        original = by_page[page_number].get(ORIGINAL_LAYER)
        ocr = by_page[page_number].get(OCR_LAYER)
        chosen = choose_text_layer(original, ocr)

        if chosen is None:
            continue
        selected.append(
            SelectedPageText(
                page_number=page_number,
                text=chosen.text,
                selected_text_layer=chosen.layer_type,
                has_text_layer=bool(normalize_pdf_text(chosen.text)),
                ocr_used=chosen.layer_type == OCR_LAYER,
            )
        )
    return selected


def article_text_layer_summary(session: Session, article: Article) -> list[dict[str, object]]:
    rows = list(session.scalars(select(PageTextLayer).where(PageTextLayer.article_id == article.id).order_by(PageTextLayer.page_number, PageTextLayer.layer_type)))
    selected = {page.page_number: page.selected_text_layer for page in select_best_pages(session, article)}
    return [
        {
            "page_number": row.page_number,
            "layer_type": row.layer_type,
            "has_usable_text": row.has_usable_text,
            "quality_score": float(row.quality_score),
            "selected": selected.get(row.page_number) == row.layer_type,
            "source_pdf_path": row.source_pdf_path,
        }
        for row in rows
    ]
