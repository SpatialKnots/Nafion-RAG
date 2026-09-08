"""Necessary experimental-context cues, not scientific entailment validation.

Version 1 deliberately covers two question families. A match can only preserve
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
            matched = [cue for cue in cues if has(cue, text)]
            fragments.append({"evidence_index": index, "matched": matched,
                              "missing": [cue for cue in cues if cue not in matched]})
        details[relation] = {
            "required_cues": list(cues), "fragments": fragments,
            "matching_evidence_indices": [item["evidence_index"] for item in fragments if not item["missing"]],
        }
    return {
        "version": 1, "scope": "necessary_context_cues_not_entailment",
        "required": list(requirements),
        "missing": [relation for relation, detail in details.items() if not detail["matching_evidence_indices"]],
        "details": details,
    }
