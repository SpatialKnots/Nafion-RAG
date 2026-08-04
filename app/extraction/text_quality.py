from __future__ import annotations

import re
from dataclasses import dataclass

MIN_TEXT_CHARS_PER_PAGE = 80
MIN_ALNUM_RATIO = 0.25
CAPTION_PATTERN = re.compile(
    r"^\s*(?:Table|Figure|Fig\.|\u0420\u0438\u0441\.|\u0422\u0430\u0431\u043b\u0438\u0446\u0430)\s*\d+[\.:]?\s+",
    flags=re.IGNORECASE | re.MULTILINE,
)
FORMULA_PATTERN = re.compile(
    r"(?:[A-Za-z\u0391-\u03a9\u03b1-\u03c9]\s*[=\u2248]\s*[^,\n;]{2,}|"
    r"[A-Za-z]{1,4}[\u2080-\u20890-9]+|[\u0394\u03bb\u03bc\u03c3\u03a9\u221e\u2211\u222b\u221a])"
)


@dataclass(frozen=True)
class TextQualitySignals:
    char_count: int
    normalized_char_count: int
    control_char_ratio: float
    caption_count: int
    table_like_line_count: int
    formula_like_line_count: int
    repeated_artifact_count: int


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


def detect_caption_lines(text: str) -> list[str]:
    return [match.group(0).strip() for match in CAPTION_PATTERN.finditer(text)]


def detect_formula_like_lines(text: str) -> list[str]:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and FORMULA_PATTERN.search(stripped):
            lines.append(stripped)
    return lines


def control_character_ratio(text: str) -> float:
    if not text:
        return 0.0
    bad = sum(1 for char in text if (ord(char) < 32 and char not in "\n\r\t") or char == "\ufffd")
    return bad / len(text)


def table_like_line_count(text: str) -> int:
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if len(stripped) < 8:
            continue
        numeric_tokens = len(re.findall(r"[-+]?\d+(?:[.,]\d+)?(?:e[-+]?\d+)?", stripped, flags=re.IGNORECASE))
        wide_gaps = len(re.findall(r"\S\s{2,}\S", stripped))
        delimiter_count = stripped.count("|") + stripped.count("\t") + stripped.count(";")
        if numeric_tokens >= 3 or wide_gaps >= 2 or delimiter_count >= 3:
            count += 1
    return count


def repeated_artifact_count(text: str) -> int:
    repeated_chars = len(re.findall(r"([^\w\s])\1{4,}", text))
    repeated_words = len(re.findall(r"\b(\w{2,})\b(?:\s+\1\b){3,}", text, flags=re.IGNORECASE))
    return repeated_chars + repeated_words


def text_quality_signals(text: str) -> TextQualitySignals:
    normalized = normalize_pdf_text(text)
    return TextQualitySignals(
        char_count=len(text),
        normalized_char_count=len(normalized),
        control_char_ratio=control_character_ratio(text),
        caption_count=len(detect_caption_lines(text)),
        table_like_line_count=table_like_line_count(text),
        formula_like_line_count=len(detect_formula_like_lines(text)),
        repeated_artifact_count=repeated_artifact_count(text),
    )
