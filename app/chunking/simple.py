from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    page_start: int
    page_end: int
    source_type: str
    text: str
    char_count: int
    token_count: int


def estimate_token_count(text: str) -> int:
    # Conservative approximation for English/Russian prose without adding tokenizer dependencies.
    return max(1, len(text.split()))


def _paragraphs(page: PageText) -> list[tuple[int, str]]:
    raw_parts = page.text.replace("\r\n", "\n").split("\n\n")
    parts = [part.strip() for part in raw_parts if part.strip()]
    if parts:
        return [(page.page_number, part) for part in parts]
    stripped = page.text.strip()
    return [(page.page_number, stripped)] if stripped else []


def chunk_pages(
    pages: list[PageText],
    target_chars: int,
    overlap_chars: int,
    source_type: str = "main_text",
) -> list[TextChunk]:
    if target_chars <= 0:
        raise ValueError("target_chars must be positive")
    if overlap_chars < 0:
        raise ValueError("overlap_chars must be non-negative")

    chunks: list[TextChunk] = []
    current_parts: list[tuple[int, str]] = []
    current_chars = 0

    def flush() -> None:
        nonlocal current_parts, current_chars
        if not current_parts:
            return
        text = "\n\n".join(part for _, part in current_parts).strip()
        page_numbers = [page for page, _ in current_parts]
        chunks.append(
            TextChunk(
                chunk_index=len(chunks),
                page_start=min(page_numbers),
                page_end=max(page_numbers),
                source_type=source_type,
                text=text,
                char_count=len(text),
                token_count=estimate_token_count(text),
            )
        )
        if overlap_chars == 0:
            current_parts = []
            current_chars = 0
            return
        overlap_parts: list[tuple[int, str]] = []
        overlap_total = 0
        for page, part in reversed(current_parts):
            if overlap_total >= overlap_chars:
                break
            overlap_parts.append((page, part))
            overlap_total += len(part)
        current_parts = list(reversed(overlap_parts))
        current_chars = sum(len(part) for _, part in current_parts)

    for page in pages:
        for page_number, paragraph in _paragraphs(page):
            paragraph_len = len(paragraph)
            if current_parts and current_chars + paragraph_len > target_chars:
                flush()
            current_parts.append((page_number, paragraph))
            current_chars += paragraph_len
            if paragraph_len >= target_chars:
                flush()
    flush()
    return chunks
