"""Finite RU/EN source-local relation proposals; never a runtime permission.

Source owners, effects and conditions remain scientifically unverified. Exact
raw spans and separate unresolved states are part of the public sidecar result.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from scripts.event_value_ownership_audit import View, recognition_view
from scripts.retrieval_ablation import CUES, LIGATURE_PAIRS

VERSION = "cross_lingual_relation_audit_v0.1"
TARGET = r"(?:(?:li|na|h)[-‑–])?(?:nafion|нафион)"
PARTICLE = r"(?:particles?|частиц\w*)"
DISPERSION = r"(?:dispersions?|дисперси\w*)"
PROPERTY = r"(?:morpholog\w*|shapes?|морфолог\w*|форм[аыуеой]*)"
SOLVENT = r"(?:solvents?|растворител\w*)"
ROLES = {"material": TARGET, "object": PARTICLE, "medium": DISPERSION, "property": PROPERTY, "variable": SOLVENT}
OWNED = (
    PROPERTY
    + r"\s+of\s+(?:the\s+)?(?:"
    + TARGET
    + r"\s+(?:dispersion\s+)?particles?|particles?\s+(?:in|of)\s+(?:(?:a|the)\s+)?"
    + TARGET
    + r"\s+dispersions?)",
    TARGET + r"\s+(?:dispersion\s+)?particles?\s+" + PROPERTY,
    PROPERTY + r"\s+частиц\w*\s+(?:дисперси\w*\s+)?" + TARGET,
)
ANTECEDENTS = (
    TARGET + r"\s+dispersions?\s+(?:contains?|contained|consists?\s+of)\s+(?:the\s+)?particles?",
    r"particles?\s+(?:in|of)\s+(?:(?:a|the)\s+)?" + TARGET + r"\s+dispersions?",
    r"частиц\w*\s+дисперси\w*\s+" + TARGET,
    r"дисперси\w*\s+" + TARGET + r"\s+содерж\w*\s+частиц\w*",
)
POSSESSIVE = re.compile(r"^\s*(?:their\s+" + PROPERTY + r"|их\s+" + PROPERTY + r")\b", re.I)
RELATIONS = {
    "variable_affects_property": SOLVENT + r"\b.*?\b(?:affect\w*|influenc\w*|chang\w*|влия\w*|меня\w*|измен\w*)\b.*?\b" + PROPERTY,
    "property_depends_on_variable": PROPERTY + r"\b.*?\b(?:depend\w*|var(?:y|ies|ied|ying)|chang\w*|завис\w*|меня\w*|измен\w*|"
    r"(?:is|was|are|were)\s+(?:strongly\s+)?(?:affected|influenced))\b.*?\b" + SOLVENT,
    "reported_nominal_effect": r"(?:effect|influence|влияни\w*)\b.*?\b" + SOLVENT + r"\b.*?\b" + PROPERTY,
}
OBSERVATION = re.compile(
    r"\b(?:observ\w*|measur\w*|found|show\w*|demonstrat\w*|reveal\w*|"
    r"наблюд\w*|измер\w*|установ\w*|показ\w*)\b",
    re.I,
)
STATUS = {
    "unperformed": r"\b(?:did|do|does)\s+not\s+(?:study|measure|investigate|test)\w*\b|"
    r"\bnot\s+(?:been\s+)?(?:studied|measured|investigated|tested)\b|"
    r"\bне\s+(?:исследовал|исследован|измерял|измерен|изучал|изучен)\w*",
    "evidence_absent": r"\bevidence\s+is\s+lacking\b|\b(?:unknown|unresolved)\b|\b(?:no|insufficient)\s+evidence\b|"
    r"\bнеизвестн\w*|\bне\s+установлен\w*|\bнет\s+данных\b",
    "future_or_proposal": r"\b(?:will|future|propos\w*|plan\w*|буд\w*|планир\w*|предстоит)\b",
    "uncertain": r"\b(?:may|might|could|would|can|should|whether|if|hypothesi\w*|perhaps|suggest\w*|"
    r"если|возможно|вероятно|предполага\w*|гипотез\w*)\b",
}
NEGATED_EFFECT = re.compile(
    r"\bnot\s+(?:affect|influenc|chang|depend)\w*|\bno\s+effect\b|"
    r"\bне\s+(?:влия\w*|меня\w*|измен\w*|завис\w*)",
    re.I,
)
ABBREVIATION = re.compile(r"\b(?:wt|vol|fig|eq|no|мас|ос|рис|табл)\.\s*$", re.I)
BOUNDARY = re.compile(r"[.!?](?=\s|$)|;|\n\s*\n|\b(?:whereas|while|but|но|тогда\s+как)\b", re.I)
NUMBER = r"\d+(?:[.,]\d+)?(?:\s*[-–—]\s*\d+(?:[.,]\d+)?)?"
FIELDS = {
    "temperature": NUMBER + r"\s*°\s*[CС]",
    "concentration": NUMBER + r"\s*(?:(?:wt|vol|mass|мас|об)\.?\s*)?%",
    "duration": NUMBER + r"\s*(?:min(?:utes?)?|hours?|days?|мин(?:ут\w*)?|ч(?:ас\w*)?|сут(?:ок)?)(?!\w)",
    "form": r"(?<!\w)(?:Li|Na|H)[-‑–](?:Nafion|Нафион)(?!\w)",
    "room_temperature": r"\b(?:room\s+temperature|комнатн\w*\s+температур\w*)\b",
}
ALLOWED_QUERY_WORDS = set(
    (
        "how does do the of in a an to on with at for nature affect affects influence influences depend depends "
        "vary varies change changes and is are their what which depending from by "
        "как меняется меняются изменяется изменяются влияет влияют зависимость зависимости зависит зависят "
        "от природы природа в на при и с для по какой какая какие форме формы the wt vol mass мас об"
    ).split()
)


def matching_view(raw: str) -> View:
    base = recognition_view(raw)
    mapping = dict(LIGATURE_PAIRS)
    pieces, positions = [], []
    for char, position in zip(base.text, base.positions, strict=True):
        expanded = mapping.get(char, char)
        pieces.append(expanded)
        positions.extend([position] * len(expanded))
    return View("".join(pieces), tuple(positions), raw)


def field_spans(view: View, start: int = 0, end: int | None = None) -> list[dict[str, Any]]:
    stop = len(view.text) if end is None else end
    return [
        {"kind": name, **view.anchor(start + match.start(), start + match.end()), "owner_established": False}
        for name, pattern in FIELDS.items()
        for match in re.finditer(pattern, view.text[start:stop], re.I)
    ]


def requirements(question: str) -> dict[str, Any]:
    view = matching_view(question)
    text = view.text.lower()
    in_scope = all(re.search(pattern, text) for pattern in CUES)
    constraints = field_spans(view)
    remainder = text
    for pattern in [*FIELDS.values(), *ROLES.values()]:
        remainder = re.sub(pattern, " ", remainder, flags=re.I)
    tokens = re.findall(r"[\w]+", remainder)
    unsupported = sorted(set(tokens) - ALLOWED_QUERY_WORDS)
    return {
        "in_scope": in_scope,
        "required_roles": list(ROLES) if in_scope else [],
        "constraints": constraints,
        "unsupported_query_tokens": unsupported if in_scope else [],
        "basis": "original_question_only",
    }


def _regions(text: str) -> list[tuple[int, int]]:
    points = {0, len(text)}
    for match in BOUNDARY.finditer(text):
        if match.group() == "." and ABBREVIATION.search(text[: match.end()]):
            continue
        points.add(match.end() if match.group()[0] in ".!?;\n" else match.start())
        if match.group()[0].isalpha():
            points.add(match.end())
    ordered = sorted(points)
    return [(a, b) for a, b in zip(ordered, ordered[1:], strict=False) if text[a:b].strip()]


def _status(text: str) -> str:
    for status, pattern in STATUS.items():
        if re.search(pattern, text, re.I):
            return status
    if "?" in text:
        return "question"
    if NEGATED_EFFECT.search(text):
        return "observed_null_effect_unverified" if OBSERVATION.search(text) else "bare_negation_unresolved"
    return "affirmative_assertion_unverified"


def source_audit(raw: str) -> dict[str, Any]:
    if not isinstance(raw, str):
        raise TypeError("Raw source must be a string")
    view = matching_view(raw)
    regions = _regions(view.text)
    records = []
    linked_field_keys = set()
    for index, (start, end) in enumerate(regions):
        text = view.text[start:end]
        role_spans = {
            name: [view.anchor(start + m.start(), start + m.end()) for m in re.finditer(pattern, text, re.I)]
            for name, pattern in ROLES.items()
        }
        if not role_spans["property"]:
            continue
        owner_links = [view.anchor(start + m.start(), start + m.end()) for pattern in OWNED for m in re.finditer(pattern, text, re.I)]
        relation_links = [
            {"template": name, **view.anchor(start + m.start(), start + m.end())}
            for name, pattern in RELATIONS.items()
            for m in re.finditer(pattern, text, re.I)
            if name != "reported_nominal_effect" or OBSERVATION.search(text)
        ]
        status = _status(text)
        antecedent = None
        if (
            not owner_links
            and POSSESSIVE.search(text)
            and index
            and not role_spans["material"]
            and not re.search(r"\b(?:membranes?|films?|мембран\w*|пл[её]н\w*|another|other|друг\w*)\b", text, re.I)
        ):
            a, b = regions[index - 1]
            previous = view.text[a:b]
            boundary = view.text[b:start]
            raw_bridge = raw[view.positions[b - 1] + 1 : view.positions[start]] if start < len(view.positions) else ""
            if (
                previous.rstrip().endswith(".")
                and not re.search(r"\n\s*\n", boundary + raw_bridge)
                and _status(previous) == "affirmative_assertion_unverified"
                and any(re.search(pattern, previous, re.I) for pattern in ANTECEDENTS)
            ):
                antecedent = view.anchor(a, b)
                for name in ("material", "object", "medium"):
                    role_spans[name] = [view.anchor(a + m.start(), a + m.end()) for m in re.finditer(ROLES[name], previous, re.I)]
                owner_links = [view.anchor(start, start + POSSESSIVE.match(text).end())]
        missing = [name for name, spans in role_spans.items() if not spans]
        reasons = []
        if missing:
            reasons.append("missing_local_roles")
        if not owner_links:
            reasons.append("explicit_target_property_attachment_missing")
        medium_attached = antecedent is not None or bool(re.search(TARGET + r"\s+dispersions?\b|\bдисперси\w*\s+" + TARGET, text, re.I))
        if not medium_attached:
            reasons.append("explicit_target_dispersion_attachment_missing")
        if not relation_links:
            reasons.append("directed_dependency_template_missing")
        if len(role_spans["property"]) != 1:
            reasons.append("multiple_property_mentions_unresolved")
        if status not in {"affirmative_assertion_unverified", "observed_null_effect_unverified"}:
            reasons.append("statement_status_not_eligible")
        fields = field_spans(view, start, end)
        candidate = not reasons
        if candidate:
            linked_field_keys.update((field["kind"], field["start"], field["end"]) for field in fields)
        records.append(
            {
                "span": view.anchor(start, end),
                "role_spans": role_spans,
                "missing_roles": missing,
                "owner_links": owner_links,
                "antecedent": antecedent,
                "relation_links": relation_links,
                "status": status,
                "candidate": candidate,
                "diagnostics": reasons,
                "fields": fields,
                "performed_established": False,
                "material_owner_established": False,
                "value_owner_established": False,
            }
        )
    all_fields = field_spans(view)
    return {
        "regions": records,
        "candidate_count": sum(row["candidate"] for row in records),
        "unassigned_fields": [field for field in all_fields if (field["kind"], field["start"], field["end"]) not in linked_field_keys],
        "scientific_admission": False,
        "normalization": "mapped_ligatures_and_word_linebreak_join_only",
    }


def _surface(text: str) -> str:
    return re.sub(r"\s+", "", matching_view(text).text).casefold()


def audit(question: str, sources: list[dict[str, Any]], *, baseline_adequate: bool) -> dict[str, Any]:
    query = requirements(question)
    if not query["in_scope"]:
        return {
            "version": VERSION,
            "requirements": query,
            "state": "out_of_scope",
            "baseline_adequate": baseline_adequate,
            "textual_requirements_met": None,
            "baseline_preserved": True,
            "scientific_admission": False,
            "sources": [],
            "duplicates": [],
        }
    analyses = []
    duplicates: dict[str, list[int]] = {}
    repeated_spans: dict[str, list[dict[str, int]]] = {}
    proposals = []
    for index, source in enumerate(sources):
        raw = source["text"]
        if not isinstance(raw, str):
            raise TypeError("Raw source must be a string")
        duplicates.setdefault(hashlib.sha256(raw.encode()).hexdigest(), []).append(index)
        analysis = source_audit(raw)
        analyses.append({"evidence_index": index, **analysis})
        for region_index, region in enumerate(analysis["regions"]):
            if not region["candidate"]:
                continue
            repeated_spans.setdefault(hashlib.sha256(region["span"]["text"].encode()).hexdigest(), []).append(
                {"evidence_index": index, "region_index": region_index}
            )
            field_checks = [
                {
                    "required": field,
                    "exact_local_surface_present": any(
                        local["kind"] == field["kind"] and _surface(local["text"]) == _surface(field["text"]) for local in region["fields"]
                    ),
                    "owner_established": False,
                }
                for field in query["constraints"]
            ]
            proposals.append(
                {
                    "evidence_index": index,
                    "region_index": region_index,
                    "field_checks": field_checks,
                    "requested_condition_owner_established": False,
                    "textual_requirements_met": not query["unsupported_query_tokens"] and not field_checks,
                }
            )
    met = any(proposal["textual_requirements_met"] for proposal in proposals)
    return {
        "version": VERSION,
        "requirements": query,
        "sources": analyses,
        "proposals": proposals,
        "duplicates": [
            {"raw_text_sha256": digest, "evidence_indices": indices, "policy": "report_only_keep_all_source_addresses"}
            for digest, indices in duplicates.items()
            if len(indices) > 1
        ],
        "repeated_proposal_spans": [
            {"raw_span_sha256": digest, "addresses": addresses} for digest, addresses in repeated_spans.items() if len(addresses) > 1
        ],
        "state": "textual_relation_candidate_unverified" if met else "unresolved_requested_relation",
        "textual_requirements_met": met,
        "baseline_adequate": baseline_adequate,
        "baseline_preserved": True,
        "baseline_disagreement": met != baseline_adequate,
        "scientific_admission": False,
        "independent_accuracy": None,
    }
