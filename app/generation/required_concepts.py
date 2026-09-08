"""Conservative, versioned identity aliases for explicitly named query substances.

This is an initial catalogue, not general chemical entity recognition. Each entry
is one identity, never a topical group (for example EC and SL are separate).
Mention coverage is necessary, not proof of a scientific claim or relationship.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

CATALOGUE_VERSION = 1
IDENTITY_ALIASES: dict[str, tuple[str, ...]] = {
    "polybenzimidazole": ("polybenzimidazole", "PBI", "полибензимидазол", "полибензимидазола", "полибензимидазолом"),
    "phosphoric_acid": (
        "phosphoric acid",
        "H3PO4",
        "фосфорная кислота",
        "фосфорной кислоты",
        "фосфорной кислотой",
        "фосфорную кислоту",
    ),
    "dimethylformamide": ("DMF", "диметилформамид", "диметилформамида", "диметилформамиде", "dimethylformamide"),
    "dimethyl_sulfoxide": (
        "DMSO",
        "dimethyl sulfoxide",
        "dimethyl sulphoxide",
        "диметилсульфоксид",
        "диметилсульфоксида",
        "диметилсульфоксиде",
    ),
    "ethylene_carbonate": ("EC", "ethylene carbonate", "этиленкарбонат", "этиленкарбоната", "этиленкарбонате"),
    "sulfolane": ("SL", "sulfolane", "сульфолан", "сульфолана", "сульфолане"),
    "diglyme": ("diglyme", "diethylene glycol dimethyl ether", "диглим", "диглима", "диглиме"),
}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[\s\-‐‑–—]+", " ", text)


def _matches(alias: str, text: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(_normalize(alias)) + r"(?!\w)", text) is not None


@dataclass(frozen=True)
class RequiredConceptCoverage:
    required: list[str]
    matched: list[str]
    missing: list[str]
    details: dict[str, dict[str, list[str]]]
    catalogue_version: int = CATALOGUE_VERSION


def assess_required_concepts(question: str, evidence_texts: Sequence[str]) -> RequiredConceptCoverage:
    query = _normalize(question)
    # Match each fragment independently: phrase halves in separate chunks do not
    # establish an identity, even though coverage may span several sources.
    texts = [_normalize(text) for text in evidence_texts]
    required: list[str] = []
    matched: list[str] = []
    missing: list[str] = []
    details: dict[str, dict[str, list[str]]] = {}
    for concept, aliases in IDENTITY_ALIASES.items():
        query_aliases = [alias for alias in aliases if _matches(alias, query)]
        if not query_aliases:
            continue
        evidence_aliases = [alias for alias in aliases if any(_matches(alias, text) for text in texts)]
        required.append(concept)
        (matched if evidence_aliases else missing).append(concept)
        details[concept] = {"query_aliases": query_aliases, "evidence_aliases": evidence_aliases}
    return RequiredConceptCoverage(required, matched, missing, details)
