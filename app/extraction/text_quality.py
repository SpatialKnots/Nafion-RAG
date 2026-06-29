from __future__ import annotations

import re

MIN_TEXT_CHARS_PER_PAGE = 80
MIN_ALNUM_RATIO = 0.25


def normalize_pdf_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def has_usable_text_layer(page_texts: list[str]) -> bool:
    if not page_texts:
        return False
    usable_pages = 0
    for text in page_texts:
        normalized = normalize_pdf_text(text)
        if len(normalized) < MIN_TEXT_CHARS_PER_PAGE:
            continue
        alnum_count = sum(char.isalnum() for char in normalized)
        if alnum_count / max(len(normalized), 1) >= MIN_ALNUM_RATIO:
            usable_pages += 1
    return usable_pages >= max(1, len(page_texts) // 2)


def should_run_ocr(page_texts: list[str], ocr_enabled: bool) -> bool:
    return ocr_enabled and not has_usable_text_layer(page_texts)
