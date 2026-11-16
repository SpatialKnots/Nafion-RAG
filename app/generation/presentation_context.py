"""Display-only lexical context selection and finite composition-scope notices."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.generation.required_concepts import IDENTITY_ALIASES, assess_required_concepts

NUMBER = re.compile(r"(?<![\w.,])[-+−]?\d+(?:[.,]\d+)?(?!\w|[.,]\d)")
PAIR = re.compile(r"(?<!\w)([A-Z][A-Z0-9]{1,7})\s*/\s*([A-Z][A-Z0-9]{1,7})(?!\w)")
MIXTURE = re.compile(r"\bmixtures?\b|\bblends?\b|смес[ьиьюяе]|смесь", re.I)
DISPLAY_STOP_WORDS = set("in from the and with for at to of is are be as this that by or от до при для как это из на по".split())


@dataclass(frozen=True)
class DisplayExcerpt:
    text: str
    start: int
    end: int
    matched_numbers: tuple[str, ...]
    matched_terms: tuple[str, ...]
    method: str = "literal_number_term_context_v0.1"


def _normal(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold().replace("−", "-").replace(",", ".")


def _numbers(text: str) -> set[str]:
    return {_normal(m[0]) for m in NUMBER.finditer(text)}


def _terms(text: str) -> set[str]:
    return {term for term in re.findall(r"[^\W\d_][\w-]*", _normal(text))
            if len(term) >= 2 and term not in DISPLAY_STOP_WORDS}


def display_excerpt(text: str, claim_text: str, question: str, *, limit: int = 1100) -> DisplayExcerpt:
    """Return an exact contiguous source slice, never a new supporting assertion.

    The fixed display window does not change retrieval, generation or any gate.
    A number match is only a navigation cue; it establishes no owner or relation.
    """
    numbers = _numbers(claim_text) - {"10"}
    terms = _terms(claim_text + " " + question)
    boundaries = [0, *(m.end() for m in re.finditer(r"(?<=[.!?])\s+(?=[A-ZА-ЯЁ])|\n\s*\n", text)), len(text)]
    candidates = {(0, min(limit, len(text)))}
    anchors = [m.start() for m in NUMBER.finditer(text) if _normal(m[0]) in numbers]
    anchors += [m.start() for m in re.finditer(r"[^\W\d_][\w-]*", text) if _normal(m[0]) in terms]
    for anchor in anchors:
        starts = [b for b in boundaries if max(0, anchor - limit) <= b <= anchor]
        for start in starts[-3:] or [max(0, anchor - limit // 2)]:
            ends = [b for b in boundaries if anchor < b <= start + limit]
            for end in ends or [min(len(text), start + limit)]:
                if start <= anchor < end:
                    candidates.add((start, end))

    def matches(start: int, end: int) -> tuple[set[str], set[str]]:
        return _numbers(text[start:end]) & numbers, _terms(text[start:end]) & terms

    def rank(span: tuple[int, int]) -> tuple[int, int, int, int]:
        start, end = span
        nums, words = matches(start, end)
        # Decimal mantissas distinguish measured values from common years/counts.
        return sum(3 if "." in n else 1 for n in nums), len(words), -(end - start), -start

    start, end = max(candidates, key=rank)
    # Keep a preceding sentence for ownership/conditions (e.g. "Its conductivity")
    # and stop after the last matching number's sentence. This is surrounding
    # context, not resolution of that owner or a scientific support judgment.
    numeric_hits = [m for m in NUMBER.finditer(text, start, end) if _normal(m[0]) in numbers]
    if numeric_hits:
        following = [b for b in boundaries if numeric_hits[-1].end() <= b <= end]
        if following:
            end = min(following)
        previous = [b for b in boundaries if b < start]
        if previous and end - previous[-1] <= limit:
            start = previous[-1]
    nums, words = matches(start, end)
    return DisplayExcerpt(text[start:end], start, end, tuple(sorted(nums)), tuple(sorted(words)))


def mixture_scope_notes(question: str, claim_text: str, source_text: str) -> list[str]:
    """Finite surface notice, not purity inference, semantic validation or a gate."""
    requested = set(assess_required_concepts(question, []).required)
    if not requested or MIXTURE.search(question):
        return []
    notes = []
    for match in PAIR.finditer(claim_text):
        components = [set(assess_required_concepts(name, []).required) for name in match.groups()]
        if any(len(component) != 1 for component in components):
            continue
        identities = set.union(*components)
        named = identities & requested
        if len(identities) != 2 or len(named) != 1:
            continue
        # Require a literal pair and mixture cue in the cited model context too;
        # an unrelated extra solvent mention is insufficient for this notice.
        pair = re.compile(r"(?<!\w)" + re.escape(match[1]) + r"\s*/\s*" + re.escape(match[2]) + r"(?!\w)")
        occurrences = list(pair.finditer(source_text))
        if not any(MIXTURE.search(source_text[max(0, m.start() - 150):m.end() + 150]) for m in occurrences):
            continue
        identity, = named
        aliases = IDENTITY_ALIASES[identity]
        name = next((part for part in match.groups() if part in aliases), aliases[0])
        notes.append(f"Вопрос называет {name}; в ответе и цитируемом контексте указана смесь {match[1]}/{match[2]}. "
                     f"Данные для этой смеси не устанавливают свойства чистого {name}.")
    return list(dict.fromkeys(notes))
