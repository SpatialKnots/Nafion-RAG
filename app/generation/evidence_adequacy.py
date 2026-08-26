from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

LIGATURES = str.maketrans({"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"})
DOMAIN_TERM_SYNONYMS = {
    "lithiation": ["li-nafion", "lithiated nafion", "lithium form", "converted to the lithium form"],
    "protocol": ["experimental", "prepared", "preparation", "procedure", "method"],
}

COMMON_QUERY_TERMS = {
    "and",
    "are",
    "application",
    "battery",
    "cell",
    "electrochemical",
    "electrolyte",
    "fuel",
    "how",
    "ionomer",
    "lithium",
    "membrane",
    "membranes",
    "perfluorosulfonic",
    "polymer",
    "properties",
    "solution",
    "solutions",
    "solvent",
    "solvents",
    "system",
    "systems",
    "the",
    "what",
    "using",
    "was",
    "water",
    "were",
    "with",
    "водные",
    "водой",
    "для",
    "мембран",
    "мембрана",
    "мембраны",
    "нафион",
    "проводимость",
    "раствор",
    "растворами",
    "растворитель",
}


class EvidenceText(Protocol):
    @property
    def text(self) -> str: ...


@dataclass(frozen=True)
class EvidenceAdequacy:
    adequate: bool
    query_terms: list[str]
    distinctive_terms: list[str]
    matched_terms: list[str]
    top_matched_terms: list[str]
    coverage: float
    top_coverage: float
    reason: str


def assess_evidence_adequacy(question: str, evidence: Sequence[EvidenceText]) -> EvidenceAdequacy:
    query_terms = _query_terms(question)
    distinctive_terms = [term for term in query_terms if term not in COMMON_QUERY_TERMS]
    if not evidence:
        return EvidenceAdequacy(False, query_terms, distinctive_terms, [], [], 0.0, 0.0, "no_evidence")
    if not distinctive_terms:
        return EvidenceAdequacy(False, query_terms, distinctive_terms, [], [], 0.0, 0.0, "no_distinctive_query_terms")

    all_text = "\n".join(item.text for item in evidence).lower().translate(LIGATURES)
    top_text = evidence[0].text.lower().translate(LIGATURES)
    matched_terms = [term for term in distinctive_terms if _term_matches_text(term, all_text)]
    top_matched_terms = [term for term in distinctive_terms if _term_matches_text(term, top_text)]
    coverage = len(matched_terms) / len(distinctive_terms)
    top_coverage = len(top_matched_terms) / len(distinctive_terms)
    if len(distinctive_terms) <= 2:
        adequate = len(matched_terms) >= 1
    else:
        adequate = (
            (len(matched_terms) >= 2 and coverage >= 0.6)
            or (len(top_matched_terms) >= 2 and top_coverage >= 0.5)
            or (len(matched_terms) >= 5 and len(top_matched_terms) >= 2)
        )
    reason = "sufficient_distinctive_term_coverage" if adequate else "insufficient_distinctive_term_coverage"
    return EvidenceAdequacy(
        adequate=adequate,
        query_terms=query_terms,
        distinctive_terms=distinctive_terms,
        matched_terms=matched_terms,
        top_matched_terms=top_matched_terms,
        coverage=coverage,
        top_coverage=top_coverage,
        reason=reason,
    )


def _query_terms(question: str) -> list[str]:
    raw_terms = re.findall(r"[\w-]+", question.lower().translate(LIGATURES), flags=re.UNICODE)
    return [term.strip("-") for term in raw_terms if len(term.strip("-")) >= 3]


def _term_matches_text(term: str, text: str) -> bool:
    if term in text:
        return True
    return any(synonym in text for synonym in DOMAIN_TERM_SYNONYMS.get(term, []))
