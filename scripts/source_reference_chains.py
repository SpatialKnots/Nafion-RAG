"""Finite explicit reference paths; old v0.4 decisions stay unchanged."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from scripts import component_context_relations_v04 as v4
from scripts import cross_lingual_relation_audit as v1
from scripts import typed_partial_relations as v2
from scripts.prepare_source_reference_cases import REFERENCE_PATTERN

VERSION = "source_reference_chains_v0.5"
MAX_REFERENCE_HOPS = 3
PAIR = r"(?P<pair>(?P<left>" + v2.COMPONENT + r")\s*/\s*(?P<right>" + v2.COMPONENT + r"))"
DECLARATIONS = [
    re.compile(r"(?<!\w)(?P<target>" + v1.TARGET + r")\s+dispersions?\s+"
               r"(?:(?:contains?|contained)\s+(?P<object>particles?)\s+)?in\s+(?:the\s+)?"
               + PAIR + r"\s+(?:solvent\s+)?mixtures?\b", re.I),
    re.compile(r"\bдисперси\w*\s+(?P<target>" + v1.TARGET + r")\s+"
               r"(?:содерж\w*\s+(?P<object>частиц\w*)\s+)?в\s+(?:смеси\s+)?" + PAIR, re.I),
]
REF = re.compile(REFERENCE_PATTERN, re.I)
POSSIBLE = re.compile(r"\b(?:possible|possibly|probably|hypothetical|вероятн\w*|возможн\w*)\b", re.I)
PAIR_SURFACE = re.compile(v2.COMPONENT + r"\s*/\s*" + v2.COMPONENT, re.I)
ASSOCIATION = re.compile(r"\bappear\w*\s+with\b|\bнаблюдал\w*\s+в\b", re.I)
BRIDGE = re.compile(r"^\s*(?:" + REFERENCE_PATTERN + r")\s+"
                    r"(?:contains?|contained|содерж\w*)\s+(?:the\s+)?"
                    r"(?:(?P<target>" + v1.TARGET + r")\s+)?(?P<object>" + v1.PARTICLE + r")\b\s*[.!]?\s*$", re.I)


def _guard(text: str, *, property_statement: bool = False) -> list[str]:
    reasons = []
    allowed = {"affirmative_assertion_unverified"}
    if property_statement:
        allowed.add("observed_null_effect_unverified")
    if v1._status(text) not in allowed or POSSIBLE.search(text):
        reasons.append("statement_status_not_eligible")
    if v4.CONTEXT_BLOCK.search(text):
        reasons.append("competing_object_or_material")
    if v4.EVIDENCE_ABSENCE.search(text) or v4.NEGATIVE_OBSERVATION.search(text):
        reasons.append("absence_or_negative_observation")
    if not property_statement and v4.CONTEXT_NEGATION.search(text):
        reasons.append("negated_context_unresolved")
    return reasons


def declarations(view: v1.View, a: int, b: int) -> list[dict[str, Any]]:
    text = view.text[a:b]
    rows = []
    for pattern in DECLARATIONS:
        for match in pattern.finditer(text):
            reasons = _guard(text)
            components = [match[name].casefold() for name in ("left", "right")]
            if not all(re.search(r"[a-zа-яё]", c, re.I) for c in components) or any(c in v2.DIMENSIONS for c in components):
                reasons.append("numeric_or_dimension_pair")
            if len(list(PAIR_SURFACE.finditer(text))) != 1:
                reasons.append("multiple_component_pairs_unresolved")
            targets = {m.group().casefold() for m in re.finditer(v1.TARGET, text, re.I)}
            if targets != {match["target"].casefold()}:
                reasons.append("multiple_target_forms_unresolved")
            if len(list(re.finditer(v1.PARTICLE, text, re.I))) > 1:
                reasons.append("multiple_particle_mentions_unresolved")
            rows.append({
                "span": view.anchor(a + match.start(), a + match.end()), "sentence_span": view.anchor(a, b),
                "pair_span": view.anchor(a + match.start("pair"), a + match.end("pair")),
                "components": [view.anchor(a + match.start(n), a + match.end(n)) for n in ("left", "right")],
                "target_span": view.anchor(a + match.start("target"), a + match.end("target")),
                "particle_span": view.anchor(a + match.start("object"), a + match.end("object")) if match["object"] else None,
                "solvent_surface_present": bool(re.search(v1.SOLVENT, match.group(), re.I)),
                "diagnostics": reasons, "eligible": not reasons,
            })
    if len(rows) > 1:
        for row in rows:
            row["eligible"] = False
            row["diagnostics"].append("multiple_declarations_unresolved")
    return rows


def source_graph(raw: str, query: dict[str, Any]) -> dict[str, Any]:
    view = v1.matching_view(raw)
    regions = v2.regions(view.text)
    declared = [declarations(view, a, b) for a, b in regions]
    paths, inventory = [], []
    for index, rows in enumerate(declared):
        for declaration in rows:
            record = {"region_index": index, **declaration, "attempts": []}
            inventory.append(record)
            if not declaration["eligible"]:
                continue
            hops = []
            particle = declaration["particle_span"]
            target = v1.matching_view(declaration["target_span"]["text"]).text.casefold()
            for position in range(index + 1, min(len(regions), index + 1 + MAX_REFERENCE_HOPS)):
                a, b = regions[position]
                pa, pb = regions[position - 1]
                text, previous = view.text[a:b], view.text[pa:pb]
                span = view.anchor(a, b)
                refs = list(REF.finditer(text))
                properties = list(re.finditer(v1.PROPERTY, text, re.I))
                reasons = _guard(text, property_statement=bool(properties))
                gap = raw[view.positions[pb - 1] + 1:view.positions[a]]
                if not previous.rstrip().endswith(".") or re.search(r"\n\s*\n", gap):
                    reasons.append("sentence_or_paragraph_boundary")
                if declared[position]:
                    reasons.append("new_declaration_blocks_inheritance")
                if len(refs) != 1:
                    reasons.append("missing_or_multiple_explicit_references")
                targets = {m.group().casefold() for m in re.finditer(v1.TARGET, text, re.I)}
                if targets and targets != {target}:
                    reasons.append("target_form_mismatch")
                attempt = {"region_index": position, "span": span, "diagnostics": reasons}
                record["attempts"].append(attempt)
                if reasons:
                    break
                ref = refs[0]
                reference = view.anchor(a + ref.start(), a + ref.end())
                bridge = BRIDGE.search(text)
                if bridge and not properties:
                    particle = view.anchor(a + bridge.start("object"), a + bridge.end("object"))
                    hops.append({"kind": "explicit_particle_reference", "span": span, "reference_span": reference,
                                 "particle_span": particle})
                    continue
                if len(properties) != 1:
                    reasons.append("property_endpoint_missing_or_multiple")
                    break
                prop = properties[0]
                if prop.end() >= ref.start():
                    reasons.append("property_to_reference_direction_unresolved")
                    break
                if text[ref.end():].strip() not in {"", ".", "!"}:
                    reasons.append("unparsed_reference_tail_unresolved")
                    break
                between = text[prop.end():ref.start()]
                predicate = v2.PREDICATES["property_depends_on_variable"].search(between)
                association = ASSOCIATION.search(between)
                if predicate is None and association is None:
                    reasons.append("directed_property_predicate_missing")
                    break
                variables = v2.variable_nodes(view, a, b)
                if any(n["kind"] != "literal_solvent" for n in variables) or len(variables) > 1:
                    reasons.append("competing_variable_unresolved")
                    break
                if v2.OTHER_PROPERTY.search(text):
                    reasons.append("competing_property_unresolved")
                    break
                owned = [view.anchor(a + m.start(), a + m.end()) for pattern in v1.OWNED for m in re.finditer(pattern, text, re.I)]
                possessive = v1.POSSESSIVE.search(text)
                explicit_target_property = re.search(v1.TARGET + r"\s+" + v1.PROPERTY, text, re.I)
                if not owned and not (possessive and particle is not None) and not explicit_target_property:
                    reasons.append("target_property_attachment_unresolved")
                    break
                chosen = predicate or association
                assert chosen is not None
                kind = "directed_dependency" if predicate else "context_association"
                property_span = view.anchor(a + prop.start(), a + prop.end())
                local_particles = [view.anchor(a + m.start(), a + m.end()) for m in re.finditer(v1.PARTICLE, text, re.I)]
                attachment = owned or ([view.anchor(a + possessive.start(), a + possessive.end())] if possessive else
                                       [view.anchor(a + explicit_target_property.start(), a + explicit_target_property.end())])
                particle_attached = bool(owned and local_particles) or bool(possessive and particle is not None)
                solvent = declaration["solvent_surface_present"] or bool(re.search(v1.SOLVENT, ref.group(), re.I))
                missing = []
                if not particle_attached:
                    missing.append("particle_property_attachment_unresolved")
                if not solvent:
                    missing.append("explicit_solvent_role_unresolved")
                if kind != "directed_dependency":
                    missing.append("context_association_is_not_dependency")
                hops.append({
                    "kind": kind, "span": span, "reference_span": reference, "property_span": property_span,
                    "predicate_span": view.anchor(a + prop.end() + chosen.start(), a + prop.end() + chosen.end()),
                    "target_attachment": attachment, "particle_antecedent_span": particle,
                    "status": v1._status(text),
                })
                complete = not missing
                paths.append({
                    "declaration_region": index, "property_region": position, "declaration": declaration,
                    "hops": hops, "relation_kind": kind, "missing_roles": missing,
                    "complete_chain_roles": complete,
                    "textual_requirements_met": complete and not query["constraints"] and not query["unsupported_query_tokens"],
                    "scientific_admission": False, "chemical_identity_established": False,
                    "performed_established": False, "material_owner_established": False, "value_owner_established": False,
                })
                break
            else:
                if len(hops) == MAX_REFERENCE_HOPS:
                    record.setdefault("path_diagnostics", []).append("reference_hop_limit_reached")
    references = []
    linked = {(h["reference_span"]["start"], h["reference_span"]["end"]) for p in paths for h in p["hops"]}
    for a, b in regions:
        for match in REF.finditer(view.text[a:b]):
            span = view.anchor(a + match.start(), a + match.end())
            bound = (span["start"], span["end"]) in linked
            references.append({"span": span, "sentence_span": view.anchor(a, b), "linked": bound,
                               "diagnostics": _guard(view.text[a:b], property_statement=True)
                               + ([] if bound else ["no_eligible_explicit_reference_path"])})
    return {"declarations": inventory, "references": references, "paths": paths, "scientific_admission": False}


def audit(question: str, sources: list[dict[str, Any]], *, baseline_adequate: bool) -> dict[str, Any]:
    result = v4.audit(question, sources, baseline_adequate=baseline_adequate)
    result["version"] = VERSION
    graphs, paths, groups = [], [], {}
    if result["requirements"]["in_scope"]:
        for index, source in enumerate(sources):
            graph = source_graph(source["text"], result["requirements"])
            graphs.append({"evidence_index": index, **graph})
            for path_index, path in enumerate(graph["paths"]):
                address = {"evidence_index": index, "path_index": path_index}
                paths.append({**address, "complete_chain_roles": path["complete_chain_roles"],
                              "textual_requirements_met": path["textual_requirements_met"], "scientific_admission": False})
                digest = hashlib.sha256("\0".join([path["declaration"]["span"]["text"],
                                                   *[h["span"]["text"] for h in path["hops"]]]).encode()).hexdigest()
                groups.setdefault(digest, []).append(address)
    result.update(
        chain_sources=graphs, source_chains=paths,
        chain_textual_requirements_met=any(p["textual_requirements_met"] for p in paths) if result["requirements"]["in_scope"] else None,
        exact_chain_groups=[{"raw_chain_sha256": digest, "addresses": addresses} for digest, addresses in groups.items()],
    )
    return result
