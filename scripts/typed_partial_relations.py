"""Offline typed partial graph; no relation/condition becomes a runtime permit.

Component names are source surfaces, not resolved chemical or solvent entities.
The segmentation adapter is serialized and restores the immutable v0.1 reader.
"""

from __future__ import annotations

import bisect
import hashlib
import re
from typing import Any
from unittest.mock import patch

from scripts import cross_lingual_relation_audit as v1

VERSION = "typed_partial_relations_v0.2"
ABBREVIATION = re.compile(r"\b(?:ca|e\.g|i\.e|etc|wt|vol|fig|eq|no|мас|ос|рис|табл)\.\s*$", re.I)
COMPONENT = r"[a-zа-яё0-9](?:[\w+()–-]|(?<=-)\s*\n\s*(?=\w))*"
RATIO = re.compile(
    r"(?P<left>" + COMPONENT + r")\s*/\s*(?P<right>" + COMPONENT + r")\s+"
    r"(?:(?:mass|volume|molar|массов\w*|объ[её]мн\w*)\s+)?(?P<binding>solvent\s+)?"
    r"(?:ratios?|соотношени\w*)\b",
    re.I,
)
DIMENSIONS = {"length", "diameter", "height", "width", "radius", "длина", "диаметр", "высота", "ширина", "радиус"}
OTHER_PROPERTY = re.compile(r"\b(?:conductivit\w*|swelling|viscosity|pressure|проводимост\w*|набухани\w*|вязкост\w*|давлени\w*)\b", re.I)
PREDICATES = {
    "property_depends_on_variable": re.compile(
        r"\b(?:(?:is|was|are|were)\s+(?:strongly\s+)?(?:affected|influenced)\s+by|"
        r"depend\w*|var(?:y|ies|ied|ying)|chang\w*|завис\w*|меня\w*|измен\w*)\b",
        re.I,
    ),
    "variable_affects_property": re.compile(r"\b(?:affect\w*|influenc\w*|chang\w*|влия\w*|меня\w*|измен\w*)\b", re.I),
}
VARIABLE_WORDS = {
    "literal_solvent": v1.SOLVENT,
    "temperature": r"\b(?:temperature\w*|температур\w*)\b",
    "polymer_concentration_surface": r"\b(?:polymer|Nafion)\s+concentration\w*\b|"
    r"\bконцентраци\w*\s+(?:полимер\w*|Nafion)\b",
    "concentration_owner_unresolved": r"\b(?:concentration\w*|content|концентраци\w*|содержани\w*)\b",
}


def regions(text: str) -> list[tuple[int, int]]:
    points = {0, len(text)}
    for boundary in v1.BOUNDARY.finditer(text):
        if boundary.group() == "." and ABBREVIATION.search(text[: boundary.end()]):
            continue
        points.add(boundary.end() if boundary.group()[0] in ".!?;\n" else boundary.start())
        if boundary.group()[0].isalpha():
            points.add(boundary.end())
    ordered = sorted(points)
    return [(a, b) for a, b in zip(ordered, ordered[1:], strict=False) if text[a:b].strip()]


def segmentation_only(question: str, sources: list[dict[str, Any]], *, baseline_adequate: bool) -> dict[str, Any]:
    # Explicitly offline/serialized: do not mount this adapter in app generation.
    with patch.object(v1, "_regions", regions):
        return v1.audit(question, sources, baseline_adequate=baseline_adequate)


def variable_nodes(view: v1.View, start: int, end: int) -> list[dict[str, Any]]:
    text = view.text[start:end]
    nodes = []
    for match in RATIO.finditer(text):
        components = [
            {"surface": match[name], "span": view.anchor(start + match.start(name), start + match.end(name))} for name in ("left", "right")
        ]
        surfaces = [component["surface"].casefold() for component in components]
        if not all(re.search(r"[a-zа-яё]", surface, re.I) for surface in surfaces):
            kind = "unassigned_numeric_ratio"
        elif any(surface in DIMENSIONS for surface in surfaces):
            kind = "dimension_ratio"
        else:
            kind = "named_component_ratio"
        nodes.append(
            {
                "kind": kind,
                "span": view.anchor(start + match.start(), start + match.end()),
                "components": components,
                "solvent_binding": "explicit_lexical" if match["binding"] else "unresolved",
                "chemical_identity_established": False,
                "value_owner_established": False,
            }
        )
    for kind, pattern in VARIABLE_WORDS.items():
        for match in re.finditer(pattern, text, re.I):
            span = view.anchor(start + match.start(), start + match.end())
            if any(node["span"]["start"] <= span["start"] < span["end"] <= node["span"]["end"] for node in nodes):
                continue
            nodes.append(
                {
                    "kind": kind,
                    "span": span,
                    "components": [],
                    "solvent_binding": "literal_variable" if kind == "literal_solvent" else "not_established",
                    "chemical_identity_established": False,
                    "value_owner_established": False,
                }
            )
    return sorted(nodes, key=lambda node: node["span"]["start"])


def _edge(view: v1.View, unit: dict[str, Any], variable: dict[str, Any], variable_count: int) -> dict[str, Any] | None:
    properties = unit["role_spans"]["property"]
    if len(properties) != 1:
        return None
    prop, endpoint = properties[0], variable["span"]
    if prop["end"] <= endpoint["start"]:
        direction, a, b = "property_depends_on_variable", prop["end"], endpoint["start"]
    elif endpoint["end"] <= prop["start"]:
        direction, a, b = "variable_affects_property", endpoint["end"], prop["start"]
    else:
        return None
    start = bisect.bisect_left(view.positions, a)
    end = bisect.bisect_left(view.positions, b)
    bridge = view.text[start:end]
    predicate = PREDICATES[direction].search(bridge)
    if predicate is None:
        return None
    blocked = []
    if not unit["owner_links"]:
        blocked.append("target_property_attachment_unresolved")
    if unit["status"] not in {"affirmative_assertion_unverified", "observed_null_effect_unverified"}:
        blocked.append("statement_status_not_eligible")
    if variable_count != 1:
        blocked.append("multiple_variable_nodes_unresolved")
    if OTHER_PROPERTY.search(bridge):
        blocked.append("intervening_other_property")
    if variable["kind"] == "unassigned_numeric_ratio":
        blocked.append("ratio_components_unassigned")
    scope = (
        "explicit_solvent_variable"
        if variable["solvent_binding"] in {"literal_variable", "explicit_lexical"}
        else (
            "different_variable_type"
            if variable["kind"] in {"dimension_ratio", "temperature", "polymer_concentration_surface", "concentration_owner_unresolved"}
            else "component_ratio_solvent_scope_unresolved"
        )
    )
    return {
        "span": unit["span"],
        "property_span": prop,
        "variable": variable,
        "direction": direction,
        "predicate_span": view.anchor(start + predicate.start(), start + predicate.end()),
        "target_attachment": unit["owner_links"],
        "antecedent": unit["antecedent"],
        "status": unit["status"],
        "partial_relation": not blocked,
        "diagnostics": blocked,
        "query_variable_scope": scope,
        "strict_missing_roles": unit["missing_roles"],
        "fields": unit["fields"],
        "scientific_admission": False,
        "performed_established": False,
        "material_owner_established": False,
        "value_owner_established": False,
    }


def audit(question: str, sources: list[dict[str, Any]], *, baseline_adequate: bool) -> dict[str, Any]:
    strict = segmentation_only(question, sources, baseline_adequate=baseline_adequate)
    if not strict["requirements"]["in_scope"]:
        return {**strict, "version": VERSION, "partial_relations": [], "typed_sources": [], "exact_relation_groups": []}
    typed_sources, partials = [], []
    groups: dict[str, list[dict[str, int]]] = {}
    for source in strict["sources"]:
        index = source["evidence_index"]
        view = v1.matching_view(sources[index]["text"])
        units = []
        for unit_index, unit in enumerate(source["regions"]):
            a = bisect.bisect_left(view.positions, unit["span"]["start"])
            b = bisect.bisect_left(view.positions, unit["span"]["end"])
            variables = variable_nodes(view, a, b)
            edges = [edge for node in variables if (edge := _edge(view, unit, node, len(variables))) is not None]
            units.append({"region_index": unit_index, "span": unit["span"], "variables": variables, "edges": edges})
            for edge_index, edge in enumerate(edges):
                if not edge["partial_relation"]:
                    continue
                address = {"evidence_index": index, "region_index": unit_index, "edge_index": edge_index}
                complete = edge["query_variable_scope"] == "explicit_solvent_variable" and any(
                    proposal["evidence_index"] == index and proposal["region_index"] == unit_index and proposal["textual_requirements_met"]
                    for proposal in strict.get("proposals", [])
                )
                partials.append(
                    {
                        **address,
                        "query_variable_scope": edge["query_variable_scope"],
                        "complete_requirements": complete,
                        "scientific_admission": False,
                    }
                )
                key = hashlib.sha256(
                    (edge["span"]["text"] + "\0" + edge["variable"]["kind"] + "\0" + edge["direction"]).encode()
                ).hexdigest()
                groups.setdefault(key, []).append(address)
        typed_sources.append({"evidence_index": index, "units": units})
    complete = any(edge["complete_requirements"] for edge in partials)
    return {
        **strict,
        "version": VERSION,
        "typed_sources": typed_sources,
        "partial_relations": partials,
        "strict_textual_requirements_met": strict["textual_requirements_met"],
        "textual_requirements_met": complete,
        "exact_relation_groups": [{"raw_relation_sha256": digest, "addresses": addresses} for digest, addresses in groups.items()],
        "state": "complete_textual_relation_unverified"
        if complete
        else "partial_source_relation_unverified"
        if partials
        else "unresolved_requested_relation",
        "normalization": "mapped v0.1 view; v0.2 sentence abbreviations; no chemical/solvent entity inference",
    }
