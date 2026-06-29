from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz  # type: ignore[import-untyped]


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str


def extract_pages(pdf_path: Path) -> list[ExtractedPage]:
    pages: list[ExtractedPage] = []
    with fitz.open(pdf_path) as document:
        for index, page in enumerate(document, start=1):
            pages.append(ExtractedPage(page_number=index, text=page.get_text("text")))
    return pages
