"""External benchmark receipt and source quote checks; no inference or scoring."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Any

from scripts import cross_lingual_relation_audit as source_view

VERSION = "external_user_benchmark_intake_v0.1"
DASHES = dict.fromkeys(map(ord, "‐‑‒–—−"), "-")


def registered_pdf(path: str, selection: list[dict[str, Any]]) -> dict[str, Any]:
    """Resolve only drawn corpus paths, then reject any changed PDF bytes."""
    resolved = Path(path).resolve()
    records = [row for row in selection if Path(row["original_pdf_path"]).resolve() == resolved]
    if len(records) != 1:
        raise ValueError("Unregistered or ambiguous benchmark PDF")
    row = records[0]
    if hashlib.sha256(resolved.read_bytes()).hexdigest() != row["original_pdf_sha256"]:
        raise ValueError("Benchmark PDF hash mismatch")
    return row


def matching_view(raw: str) -> source_view.View:
    base = source_view.matching_view(raw)
    chars, positions = [], []
    for char, position in zip(base.text, base.positions, strict=True):
        for expanded in unicodedata.normalize("NFKC", char).casefold().translate(DASHES):
            if expanded.isspace():
                if chars and chars[-1] != " ":
                    chars.append(" ")
                    positions.append(position)
            else:
                chars.append(expanded)
                positions.append(position)
    if chars and chars[-1] == " ":
        chars.pop()
        positions.pop()
    return source_view.View("".join(chars), tuple(positions), raw)


def quote_match(raw: str, quote: str) -> dict[str, Any]:
    if not quote.strip():
        raise ValueError("Empty reference quote")
    point = _whole_edges_find(raw, quote)
    if point >= 0:
        return {"state": "raw_exact", "span": {"start": point, "end": point + len(quote), "text": quote}}
    source, needle = matching_view(raw), matching_view(quote).text
    if not needle:
        raise ValueError("Reference quote has no recognizable text")
    point = _whole_edges_find(source.text, needle)
    if point >= 0:
        return {"state": "mapped_typographic_match", "span": source.anchor(point, point + len(needle))}
    return {"state": "not_matched", "span": None}


def _whole_edges_find(source: str, needle: str) -> int:
    """Do not truncate a word/unit at quote boundaries, in either match arm."""
    def word(char: str) -> bool:
        return char.isalnum() or char == "_"

    for match in re.finditer(re.escape(needle), source):
        a, b = match.span()
        if a and word(needle[0]) and word(source[a - 1]):
            continue
        if b < len(source) and word(needle[-1]) and word(source[b]):
            continue
        return a
    return -1


def _section(block: str, title: str) -> str:
    match = re.search(r"(?m)^### " + re.escape(title) + r"[ \t]*\r?$", block)
    if match is None:
        raise ValueError("Missing benchmark section: " + title)
    end = re.search(r"(?m)^### ", block[match.end():])
    return block[match.end():match.end() + end.start()] if end else block[match.end():]


def parse_document(raw: str) -> list[dict[str, Any]]:
    headings = list(re.finditer(r"(?m)^## (Q\d+)[ \t]*\r?$", raw))
    if [m[1] for m in headings] != [f"Q{i:02d}" for i in range(1, 6)]:
        raise ValueError("Expected exactly ordered unique Q01–Q05")
    cases = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(raw)
        final_heading = re.search(r"(?m)^## (?!Q\d)[^\r\n]+", raw[heading.end():end])
        if final_heading:
            end = heading.end() + final_heading.start()
        block = raw[heading.end():end]
        question = re.search(r"\*\*Вопрос:\*\*[ \t]*(?P<text>[^\r\n]+)", block)
        path = re.search(r"\*\*Исходный PDF:\*\*\s*`([^`]+)`", block)
        if question is None or path is None:
            raise ValueError("Missing benchmark question/PDF")
        text = question["text"].rstrip()
        start = heading.end() + question.start("text")
        proof = _section(block, "Подтверждение")
        page, quotes = None, []
        for line in proof.splitlines():
            if not line.lstrip().startswith(">"):
                marker = re.search(r"(?:страница\s+PDF\W+|PDF\s+стр\.\s*)(\d+)", line, re.I)
                if marker:
                    page = int(marker[1])
            else:
                if page is None:
                    raise ValueError("Quote without a declared physical PDF page")
                original = line.lstrip()[1:].strip()
                matching = original
                if any(original.startswith(a) and original.endswith(b) for a, b in (("“", "”"), ("«", "»"), ('"', '"'))):
                    matching = original[1:-1]
                quotes.append({"pdf_page": page, "original_quote_markup": original, "matching_quote": matching})
        cases.append({
            "id": heading[1], "question": text,
            "question_span": {"start": start, "end": start + len(text), "text": text},
            "source_pdf_path_verbatim": path[1], "case_markdown_verbatim": raw[heading.start():end],
            "reference_answer_markdown_verbatim": _section(block, "Эталонный ответ"),
            "reference_source_section_verbatim": proof,
            "conditions_markdown_verbatim": _section(block, "Существенные условия и ограничения"),
            "quotes": quotes, "model_answer": None, "scientific_score": None,
        })
    return cases
