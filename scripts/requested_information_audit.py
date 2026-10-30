"""Offline lexical diagnostic for requested duration; never scientific admission.

No production imports or side effects. Finite RU/EN grammar, raw-string offsets.
Numbers with time units are candidates even when negated or about another stage.
Neither candidate presence nor its absence establishes source entailment.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

VERSION = "requested_information_audit_v0.1"
_REQUEST = re.compile(
    r"\b(?:точн\w*\s+(?:длительност\w*|врем\w*)|"
    r"сколько\s+(?:времени|секунд|минут|часов|суток)|"
    r"exact\s+(?:(?:dwell|holding|hold|soaking|drying|measurement)\s+)?(?:duration|time)|"
    r"how\s+(?:long|many\s+(?:seconds|minutes|hours|days)))\b",
    re.IGNORECASE,
)
_NUMBER = r"\d+(?:[.,]\d+)?(?:\s*[-–—]\s*\d+(?:[.,]\d+)?)?"
_WORDS = (r"one|two|three|four|five|six|seven|eight|nine|ten|"
          r"один|одна|одну|два|две|три|четыре|пять|шесть|семь|восемь|девять|десять")
_UNIT = (r"seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|"
         r"секунд\w*|минут\w*|час\w*|суток|сутки|дней|дня|день|"
         r"сек|мин|сут|ч|с|s|min|h|d")
_DURATION = re.compile(rf"(?<![\w.,])(?:{_NUMBER}|{_WORDS})\s*(?:{_UNIT})(?!\w)", re.IGNORECASE)


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class ClaimDuration:
    claim_index: int
    spans: tuple[Span, ...]


@dataclass(frozen=True)
class DurationAudit:
    version: str
    state: str
    requirement_spans: tuple[Span, ...]
    claims: tuple[ClaimDuration, ...]
    scientific_coverage: str = "not_evaluated"
    runtime_action: str = "none_offline_only"


def duration_spans(text: str) -> tuple[Span, ...]:
    """Exact substrings, no conversion, normalization, inference or sentence repair."""
    return tuple(Span(m.start(), m.end(), m.group()) for m in _DURATION.finditer(text))


def audit_duration(question: str, claim_texts: Sequence[str]) -> DurationAudit:
    """Report lexical candidates only; no answerable flag, score or pass verdict.

    Caller must supply claims from a structurally valid answer. Refusals,
    abstentions, invalid JSON and citation failures belong to separate layers.
    Unsupported wording stays outside the finite query grammar.
    """
    if not question.strip():
        raise ValueError("Question must be nonempty")
    if not claim_texts or any(not text.strip() for text in claim_texts):
        raise ValueError("Audit requires nonempty claims from a valid answer")
    requirements = tuple(Span(m.start(), m.end(), m.group()) for m in _REQUEST.finditer(question))
    claims = tuple(ClaimDuration(i, duration_spans(text)) for i, text in enumerate(claim_texts))
    if not requirements:
        state = "outside_finite_duration_query_scope"
    elif any(c.spans for c in claims):
        state = "duration_expression_present_unverified"
    else:
        state = "no_duration_expression_detected"
    return DurationAudit(VERSION, state, requirements, claims)
