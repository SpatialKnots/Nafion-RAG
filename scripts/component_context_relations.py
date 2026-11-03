"""Finite offline context bindings and observed nominal null; no admission.

The previous analyzers are immutable. All context is source-local and anchored;
component surfaces never establish chemical identity or quantitative owners.
"""

from __future__ import annotations

import bisect
import hashlib
import re
from typing import Any

from scripts import cross_lingual_relation_audit as v1
from scripts import typed_partial_relations as v2

VERSION = "component_context_relations_v0.3"
TARGET_DISPERSION = re.compile(
    v1.TARGET + r"\s+dispersions?\b|dispersions?\s+of\s+" + v1.TARGET
    + r"\b|дисперси\w*\s+" + v1.TARGET, re.I,
)
CONTEXT_BLOCK = re.compile(
    r"\b(?:membranes?|films?|another|other|polystyrene|мембран\w*|пл[её]н\w*|друг\w*)\b", re.I,
)
CONTEXT_NEGATION = re.compile(r"\b(?:no|not|never|neither|without|не|нет|без)\b", re.I)
NEGATIVE_OBSERVATION = re.compile(
    r"\b(?:not|never)\s+(?:been\s+)?(?:observ\w*|measur\w*|found|show\w*|detect\w*)"
    r"|\bне\s+(?:наблюд\w*|измер\w*|установ\w*|показ\w*)", re.I,
)
NOMINAL_PREFIX = re.compile(
    r"\b(?:(?:no\s+)?(?:effect|influence)\s+of\s+(?:the\s+)?"
    r"|(?:отсутстви\w*\s+)?влияни\w*\s+)$", re.I,
)
NOMINAL_BRIDGE = re.compile(r"\s+(?:on\s+(?:the\s+)?|на\s+)(?:.*\s)?$", re.I)
NULL_CUE = re.compile(r"\bno\s+(?:effect|influence)\b|\bотсутстви\w*\s+влияни\w*", re.I)


def _offsets(view: v1.View, span: dict[str, Any]) -> tuple[int, int]:
    return bisect.bisect_left(view.positions, span["start"]), bisect.bisect_left(view.positions, span["end"])


def _declarations(view: v1.View, a: int, b: int, node: dict[str, Any]) -> list[dict[str, Any]]:
    """Exact ordered pairs in finite explicit declarations, without a catalogue."""
    left, right = [re.escape(v1.matching_view(c["span"]["text"]).text) for c in node["components"]]
    pair = r"(?<!\w)(?P<pair>" + left + r"\s*(?:/|and|и)\s*" + right + r")(?!\w)"
    target = r"(?P<target>(?:" + TARGET_DISPERSION.pattern + r"))"
    tail = r"(?:\s+(?:for|of|для)\s+(?:the\s+)?" + target + r")?"
    templates = [
        ("explicit_solvent_components", pair + r"\s+(?:(?:were|are)\s+(?:used\s+as\s+)?)?solvents?\b" + tail),
        ("explicit_solvent_components", r"\bsolvent\s+mixture\s+of\s+" + pair + tail),
        ("explicit_solvent_components", r"\bрастворител\w*\s+" + pair + tail),
        ("explicit_dispersion_components", pair + r"\s+(?:mixture\s+)?dispersions?\b"),
        ("explicit_dispersion_components", target + r"\s+(?:in|using|в)\s+" + pair),
    ]
    text = view.text[a:b]
    declarations = []
    for kind, pattern in templates:
        for match in re.finditer(pattern, text, re.I):
            target_span = (
                view.anchor(a + match.start("target"), a + match.end("target"))
                if "target" in match.re.groupindex and match["target"] else None
            )
            declarations.append({
                "kind": kind,
                "span": view.anchor(a + match.start(), a + match.end()),
                "pair_span": view.anchor(a + match.start("pair"), a + match.end("pair")),
                "sentence_span": view.anchor(a, b),
                "target_dispersion_span": target_span,
                "chemical_identity_established": False,
                "value_owner_established": False,
            })
    return declarations


def bind_context(view: v1.View, unit: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    if node["kind"] != "named_component_ratio":
        return {"accepted": [], "rejected": [], "diagnostics": ["not_a_named_component_ratio"]}
    regions = v2.regions(view.text)
    a, b = _offsets(view, unit["span"])
    index = next(i for i, (start, end) in enumerate(regions) if start == a and end == b)
    accepted, rejected = [], []
    for position in range(max(0, index - 1), index + 1):
        start, end = regions[position]
        text = view.text[start:end]
        for declaration in _declarations(view, start, end, node):
            reasons = []
            if v1._status(text) != "affirmative_assertion_unverified" or NEGATIVE_OBSERVATION.search(text):
                reasons.append("context_status_not_affirmative")
            if CONTEXT_BLOCK.search(text):
                reasons.append("context_competing_object_or_material")
            if CONTEXT_NEGATION.search(text):
                reasons.append("context_negation_unresolved")
            # Every target occurrence must be the same source form as the relation.
            targets = {m.group().casefold() for m in re.finditer(v1.TARGET, text, re.I)}
            local_targets = {v1.matching_view(s["text"]).text.casefold() for s in unit["role_spans"]["material"]}
            if targets and targets != local_targets:
                reasons.append("context_target_form_mismatch")
            if position != index:
                raw_gap = view.raw[view.positions[end - 1] + 1: view.positions[a]]
                if not text.rstrip().endswith(".") or re.search(r"\n\s*\n", raw_gap):
                    reasons.append("context_sentence_or_paragraph_boundary")
                if declaration["target_dispersion_span"] is None:
                    reasons.append("prior_context_target_dispersion_missing")
            row = {**declaration, "position": "same_sentence" if position == index else "previous_sentence", "diagnostics": reasons}
            (rejected if reasons else accepted).append(row)
    return {
        "accepted": accepted, "rejected": rejected,
        "diagnostics": [] if accepted else ["no_eligible_explicit_component_context"],
    }


def nominal_edge(view: v1.View, unit: dict[str, Any], node: dict[str, Any], count: int) -> dict[str, Any] | None:
    if len(unit["role_spans"]["property"]) != 1:
        return None
    prop = unit["role_spans"]["property"][0]
    start, end = _offsets(view, unit["span"])
    va, vb = _offsets(view, node["span"])
    pa, _ = _offsets(view, prop)
    prefix = NOMINAL_PREFIX.search(view.text[start:va])
    if prefix is None or vb >= pa or not NOMINAL_BRIDGE.fullmatch(view.text[vb:pa]):
        return None
    text = view.text[start:end]
    if not v1.OBSERVATION.search(text):
        return None
    reasons = []
    if not unit["owner_links"]:
        reasons.append("target_property_attachment_unresolved")
    if unit["status"] not in {"affirmative_assertion_unverified", "observed_null_effect_unverified"}:
        reasons.append("statement_status_not_eligible")
    if NEGATIVE_OBSERVATION.search(text):
        reasons.append("negative_observation_not_an_observed_effect")
    if count != 1:
        reasons.append("multiple_variable_nodes_unresolved")
    if v2.OTHER_PROPERTY.search(view.text[vb:pa]):
        reasons.append("intervening_other_property")
    if node["kind"] == "unassigned_numeric_ratio":
        reasons.append("ratio_components_unassigned")
    return {
        "span": unit["span"], "property_span": prop, "variable": node,
        "direction": "reported_nominal_effect",
        "predicate_span": view.anchor(start + prefix.start(), start + prefix.end()),
        "target_attachment": unit["owner_links"], "antecedent": unit["antecedent"],
        "status": "observed_null_effect_unverified" if NULL_CUE.search(text) else unit["status"],
        "partial_relation": not reasons, "diagnostics": reasons,
        "strict_missing_roles": unit["missing_roles"], "fields": unit["fields"],
        "scientific_admission": False, "performed_established": False,
        "material_owner_established": False, "value_owner_established": False,
    }


def audit(question: str, sources: list[dict[str, Any]], *, baseline_adequate: bool) -> dict[str, Any]:
    result = v2.audit(question, sources, baseline_adequate=baseline_adequate)
    result["version"] = VERSION
    if not result["requirements"]["in_scope"]:
        return result
    partials, groups = [], {}
    for source in result["typed_sources"]:
        index = source["evidence_index"]
        view = v1.matching_view(sources[index]["text"])
        strict_source = next(s for s in result["sources"] if s["evidence_index"] == index)
        for typed_unit in source["units"]:
            unit = strict_source["regions"][typed_unit["region_index"]]
            nodes = typed_unit["variables"]
            for node in nodes:
                node["source_context"] = bind_context(view, unit, node)
            named = [n for n in nodes if n["kind"] == "named_component_ratio"]
            declarations = [b for n in named for b in n["source_context"]["accepted"]]
            active = []
            for node in nodes:
                # A literal word inside the exact declaration of the one ratio
                # describes its type; an independent solvent variable still blocks.
                declaration_role = len(named) == 1 and node["kind"] == "literal_solvent" and any(
                    b["kind"] == "explicit_solvent_components"
                    and b["span"]["start"] <= node["span"]["start"] < node["span"]["end"] <= b["span"]["end"]
                    for b in declarations
                )
                node["context_declaration_role"] = declaration_role
                if not declaration_role:
                    active.append(node)
            edges = []
            for node in active:
                edge = v2._edge(view, unit, node, len(active)) or nominal_edge(view, unit, node, len(active))
                if edge is None:
                    continue
                a, b = _offsets(view, unit["span"])
                if NEGATIVE_OBSERVATION.search(view.text[a:b]):
                    edge["diagnostics"].append("negative_observation_not_an_observed_effect")
                    edge["partial_relation"] = False
                bindings = node["source_context"]["accepted"]
                solvent = node["kind"] == "literal_solvent" or (
                    node["kind"] == "named_component_ratio" and (
                        node["solvent_binding"] == "explicit_lexical"
                        or any(b["kind"] == "explicit_solvent_components" for b in bindings)
                    )
                )
                edge["query_variable_scope"] = (
                    "explicit_solvent_variable" if solvent else "explicit_dispersion_components"
                    if bindings else "component_ratio_solvent_scope_unresolved"
                    if node["kind"] == "named_component_ratio" else "different_variable_type"
                )
                # A context rejection never silently confirms a relation/owner.
                edge["context_bindings"] = bindings
                edges.append(edge)
                if not edge["partial_relation"]:
                    continue
                missing = set(unit["missing_roles"]) - {"variable", "medium"}
                medium = "explicit_target_dispersion_attachment_missing" not in unit["diagnostics"] or any(
                    b["target_dispersion_span"] is not None for b in bindings
                )
                complete = (
                    solvent and medium and not missing and not result["requirements"]["constraints"]
                    and not result["requirements"]["unsupported_query_tokens"]
                )
                address = {"evidence_index": index, "region_index": typed_unit["region_index"], "edge_index": len(edges) - 1}
                partials.append({
                    **address, "query_variable_scope": edge["query_variable_scope"],
                    "complete_requirements": complete, "scientific_admission": False,
                })
                digest = hashlib.sha256(
                    (edge["span"]["text"] + "\0" + node["kind"] + "\0" + edge["direction"]).encode()
                ).hexdigest()
                groups.setdefault(digest, []).append(address)
            typed_unit["edges"] = edges
    complete = any(p["complete_requirements"] for p in partials)
    result.update(
        partial_relations=partials, textual_requirements_met=complete,
        baseline_disagreement=complete != baseline_adequate,
        exact_relation_groups=[{"raw_relation_sha256": digest, "addresses": addresses} for digest, addresses in groups.items()],
        state="complete_textual_relation_unverified" if complete else "partial_source_relation_unverified"
        if partials else "unresolved_requested_relation",
        normalization="v0.2 mapped view; exact component context; finite observed nominal effects; no value propagation",
    )
    return result
