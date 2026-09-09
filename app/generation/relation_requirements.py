"""Necessary experimental-context cues, not scientific entailment validation.

Version 3 deliberately covers two question families. A match can only preserve
an existing adequacy decision; it must never independently authorize an answer.
"""

import re
import unicodedata
from collections.abc import Sequence


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
    return re.sub(r"\s+", " ", text)


PATTERNS = {
    "dependency_question": r"affect\w*|influence\w*|depend\w*|effect\w*|влия\w*|влияет|влияют|завис\w*",
    "conductivity": r"conductivit\w*|проводимост\w*",
    "mixture": r"mixture\w*|binary|смес\w*",
    "composition": r"fraction\w*|composition\w*|content|ratios?|дол[яию]\w*|состав\w*|соотношени\w*",
    "composition_series": (
        r"varying (?:compositions?|ratios?)|(?:fraction|content|composition|ratio)\w*.{0,100}"
        r"(?:increas|decreas|depend|highest|maximum)|"
        r"(?:increas|decreas|depend|highest|maximum).{0,100}(?:fraction|content|composition|ratio)|"
        r"(?:изменени|увеличени|уменьшени|зависимост)\w*.{0,60}(?:дол|состав|соотношени)"
    ),
    "mixing_temperature": r"mixing temperature|температур\w* смешени\w*",
    "swelling": r"swelling|(?:solvent|weight|molar) uptake|набухани\w*|поглощени\w* растворител\w*",
    "heating": r"heating|нагрев\w*",
    "cooling": r"cooling|охлаждени\w*",
}


STATEMENT_EXCLUSIONS = {
    "unperformed_measurement": (
        r"\b(?:did|do|does)\s+not\s+(?:measure|investigate|study|test|perform|conduct)\w*\b|"
        r"\bnot\s+(?:been\s+)?(?:measured|investigated|studied|tested|performed|conducted)\b|"
        r"\bno\s+(?:such\s+)?(?:measurements|experiments|tests)\s+"
        r"(?:(?:were|have been)\s+)?(?:performed|conducted)\b|"
        r"\bне\s+(?:исследовал|исследован|измерял|измерен|проводил|проведен|проведён|изучал|изучен)\w*"
    ),
    "hypothesis_statement": (
        r"\bhypothesi[sz](?:e|es|ed|ing)\b|\buntested\s+hypothes(?:is|es)\b|"
        r"\b(?:выдвига\w*|предлага\w*)\s+гипотез\w*|\bнепроверенн\w*\s+гипотез\w*"
    ),
}


# Candidate local cue links for the cycle family. These do not establish sample
# identity, causal direction, or scientific entailment across statements.
# Diagnostic only: requiring these links caused a pronoun-reference regression.
LOCAL_LINKS = {
    "mixing_temperature_swelling_cycles": {
        "temperature_swelling": ("mixing_temperature", "swelling"),
        "swelling_heating": ("swelling", "heating"),
        "swelling_cooling": ("swelling", "cooling"),
    },
}


def _eligible_context(text: str, cues: tuple[str, ...]) -> tuple[dict[int, str], list[dict[str, object]]]:
    """Exclude explicit non-observations locally, never negate an entire fragment.

    Text here is normalized matching text, not a replacement for stored evidence.
    Sentence splitting and lexical status markers are intentionally heuristic.
    An observed null effect (e.g. 'did not affect') is not an unperformed test.
    """
    eligible = {}
    excluded: list[dict[str, object]] = []
    for index, statement in enumerate(re.split(r"(?<=[.!?;])\s+", text)):
        relevant = any(re.search(r"(?<!\w)(?:" + PATTERNS[cue] + r")(?!\w)", statement) for cue in cues)
        reasons = [name for name, pattern in STATEMENT_EXCLUSIONS.items() if relevant and re.search(pattern, statement)]
        if reasons:
            excluded.append({"statement_index": index, "normalized_text": statement, "reasons": reasons})
        else:
            eligible[index] = statement
    return eligible, excluded


def assess_relation_requirements(question: str, texts: Sequence[str]) -> dict[str, object]:
    query = _normalize(question)

    def has(name: str, text: str) -> bool:
        return re.search(r"(?<!\w)(?:" + PATTERNS[name] + r")(?!\w)", text) is not None

    requirements: dict[str, tuple[str, ...]] = {}
    if all(has(name, query) for name in ("dependency_question", "conductivity", "mixture", "composition")):
        requirements["mixture_composition_conductivity"] = ("conductivity", "mixture", "composition_series")
    if all(has(name, query) for name in ("dependency_question", "mixing_temperature", "swelling", "heating", "cooling")):
        requirements["mixing_temperature_swelling_cycles"] = ("mixing_temperature", "swelling", "heating", "cooling")
    details = {}
    for relation, cues in requirements.items():
        fragments = []
        for index, raw in enumerate(texts):
            text = _normalize(raw)
            statements, excluded = _eligible_context(text, cues)
            eligible_text = " ".join(statements.values())
            matched = [cue for cue in cues if has(cue, eligible_text)]
            links = {
                name: {"required_cues": list(pair),
                       "matching_statement_indices": [i for i, statement in statements.items()
                                                      if all(has(cue, statement) for cue in pair)]}
                for name, pair in LOCAL_LINKS.get(relation, {}).items()
            }
            fragments.append({"evidence_index": index, "matched": matched,
                              "missing": [cue for cue in cues if cue not in matched],
                              "raw_matched": [cue for cue in cues if has(cue, text)],
                              "excluded_statements": excluded,
                              "local_links": links,
                              "missing_local_links": [name for name, link in links.items()
                                                      if not link["matching_statement_indices"]]})
        details[relation] = {
            "required_cues": list(cues), "fragments": fragments,
            "matching_evidence_indices": [item["evidence_index"] for item in fragments if not item["missing"]],
            "local_link_candidate_indices": [item["evidence_index"] for item in fragments
                                             if not item["missing"] and not item["missing_local_links"]],
        }
    return {
        "version": 3, "scope": "necessary_context_cues_not_entailment",
        "local_links_policy": "diagnostic_only_not_adequacy_veto",
        "required": list(requirements),
        "missing": [relation for relation, detail in details.items() if not detail["matching_evidence_indices"]],
        "details": details,
    }
