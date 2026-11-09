"""Request-local textual fact bindings, separate from stored unowned numbers."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from app.generation.providers import Evidence


class FactPatternError(ValueError):
    """Unsupported or ambiguous finite source grammar; never missing science."""


@dataclass(frozen=True)
class Anchor:
    citation_id: str
    article_id: str
    chunk_id: str
    page_start: int
    page_end: int
    raw_chunk_sha256: str
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class Value:
    text: str
    source: Anchor
    normalization: str = "nfkc_dehyphenation_whitespace_only"
    numeric_value: str | None = None
    numeric_interpretation: str | None = None


@dataclass(frozen=True)
class Fact:
    property: str
    sample: Value | None
    value: Value | None
    unit: Value | None
    operation: str
    method: Value | None
    conditions: dict[str, Value]
    epistemic_status: str
    support: Anchor
    unknown_fields: tuple[str, ...] = ()
    scientific_ownership_verified: bool = False


@dataclass(frozen=True)
class Rendering:
    facts: tuple[Fact, ...]
    text: str
    arithmetic: dict[str, Any] | None = None
    grammar: str | None = None

    def data(self) -> dict[str, Any]:
        result = asdict(self)
        if self.grammar is None:
            result.pop("grammar")
        return result


class SourceView:
    """Recognize normalized text while retaining exact raw character intervals."""

    def __init__(self, source: Evidence, *, join_soft_hyphen_lines: bool = False):
        self.source = source
        raw = source.text
        hyphens = "-‐\u00ad" if join_soft_hyphen_lines else "-‐"
        omitted = {i for m in re.finditer(rf"(?<=\w)[{hyphens}]\s*\n\s*(?=\w)", raw) for i in range(m.start(), m.end())}
        chars: list[str] = []
        self.addresses: list[tuple[int, int]] = []
        for i, char in enumerate(raw):
            if i in omitted or char == "\u00ad":
                continue
            for normalized in unicodedata.normalize("NFKC", char):
                if normalized.isspace():
                    if chars and chars[-1] == " ":
                        self.addresses[-1] = (self.addresses[-1][0], i + 1)
                        continue
                    normalized = " "
                chars.append(normalized)
                self.addresses.append((i, i + 1))
        self.text = "".join(chars)

    def anchor(self, start: int, end: int) -> Anchor:
        if not 0 <= start < end <= len(self.text):
            raise FactPatternError("invalid_normalized_span")
        left, right = self.addresses[start][0], self.addresses[end - 1][1]
        s = self.source
        return Anchor(s.citation_id, s.article_id, s.chunk_id, s.page_start, s.page_end,
                      hashlib.sha256(s.text.encode()).hexdigest(), left, right, s.text[left:right])

    def one(self, pattern: str, flags: int = 0) -> re.Match[str]:
        matches = list(re.finditer(pattern, self.text, flags))
        if not matches or len({m.group() for m in matches}) != 1:
            raise FactPatternError("missing_or_ambiguous_source_pattern")
        return matches[0]

    def value(self, match: re.Match[str], group: str, *, power_of_ten: bool = False, word_number: bool = False) -> Value:
        text = match[group]
        number, rule = None, None
        if re.fullmatch(r"[−–-]?\d+(?:[.,]\d+)?", text):
            number, rule = str(Decimal(text.replace("−", "-").replace("–", "-").replace(",", "."))), "literal_decimal"
        elif power_of_ten and re.fullmatch(r"10[-−–]\d+", text):
            exponent = -int(re.split(r"[-−–]", text)[1])
            number, rule = str(Decimal(10) ** exponent), "explicit_source_power_of_ten"
        elif word_number:
            words = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
                     "seven": "7", "eight": "8", "nine": "9", "ten": "10"}
            if text in words:
                number, rule = words[text], "explicit_source_english_integer_word"
        return Value(text, self.anchor(*match.span(group)), numeric_value=number, numeric_interpretation=rule)

    def support(self, match: re.Match[str]) -> Anchor:
        return self.anchor(*match.span())

    def literal(self, text: str) -> Value:
        match = self.one(re.escape(text))
        return Value(match.group(), self.support(match))


NUMBER = r"(?<![\w.,+−–-])\d+(?:\.\d+)?(?![\w.,])"


def verify_anchor(anchor: Anchor, source: Evidence) -> None:
    if (anchor.citation_id != source.citation_id or anchor.article_id != source.article_id
            or anchor.chunk_id != source.chunk_id or (anchor.page_start, anchor.page_end) != (source.page_start, source.page_end)
            or anchor.raw_chunk_sha256 != hashlib.sha256(source.text.encode()).hexdigest()
            or not 0 <= anchor.start < anchor.end <= len(source.text)
            or source.text[anchor.start:anchor.end] != anchor.text):
        raise FactPatternError("raw_fact_binding_changed")
