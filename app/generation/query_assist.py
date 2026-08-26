from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from app.generation.evidence_adequacy import COMMON_QUERY_TERMS

DOMAIN_QUERY_TERMS = (
    "annealing",
    "casting",
    "conductivity",
    "diglyme",
    "dispersion",
    "ethylene",
    "carbonate",
    "glycerol",
    "impedance",
    "lithiated",
    "lithiation",
    "morphology",
    "Nafion",
    "perfluorosulfonate",
    "perfluorosulfonic",
    "plasticiser",
    "plasticizer",
    "protocol",
    "recast",
    "solvation",
    "sulfolane",
    "swelling",
    "thermodynamics",
    "vanadium",
)


@dataclass(frozen=True)
class QueryCorrection:
    original: str
    suggestion: str
    reason: str


@dataclass(frozen=True)
class QueryAssistance:
    corrected_query: str
    corrections: list[QueryCorrection]
    mode: str = "suggest_only"


def suggest_query_corrections(question: str, distinctive_terms: list[str], matched_terms: list[str]) -> QueryAssistance | None:
    matched = set(matched_terms)
    corrections: list[QueryCorrection] = []
    seen: set[tuple[str, str]] = set()
    for term in distinctive_terms:
        if term in matched or term in COMMON_QUERY_TERMS:
            continue
        for correction in _suggest_term_corrections(term):
            key = (correction.original, correction.suggestion)
            if key not in seen:
                seen.add(key)
                corrections.append(correction)
    if not corrections:
        return None
    corrected = question
    for correction in corrections:
        corrected = re.sub(rf"(?<!\w){re.escape(correction.original)}(?!\w)", correction.suggestion, corrected, flags=re.IGNORECASE)
    if corrected == question:
        return None
    return QueryAssistance(corrected_query=corrected, corrections=corrections)


def query_assistance_to_dict(assistance: QueryAssistance) -> dict[str, object]:
    return {
        "corrected_query": assistance.corrected_query,
        "corrections": [asdict(correction) for correction in assistance.corrections],
        "mode": assistance.mode,
    }


def _suggest_term_corrections(term: str) -> list[QueryCorrection]:
    direct = _suggest_term_correction(term)
    corrections = [direct] if direct is not None else []
    if "-" in term:
        corrections.extend(correction for part in term.split("-") for correction in [_suggest_term_correction(part)] if correction is not None)
    return corrections


def _suggest_term_correction(term: str) -> QueryCorrection | None:
    if len(term) < 5:
        return None
    best: tuple[int, str] | None = None
    for candidate in DOMAIN_QUERY_TERMS:
        normalized_candidate = candidate.lower()
        if normalized_candidate == term:
            continue
        distance = _levenshtein(term, normalized_candidate)
        if distance <= 2 and (best is None or distance < best[0] or (distance == best[0] and candidate < best[1])):
            best = (distance, candidate)
    if best is None:
        return None
    return QueryCorrection(original=term, suggestion=best[1], reason=f"edit_distance_{best[0]}")


def _levenshtein(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            current.append(
                min(
                    previous[right_index] + 1,
                    current[right_index - 1] + 1,
                    previous[right_index - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]
