"""Source-local owned particle/property/direction sidecar; no runtime admission."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from scripts import component_context_relations_v04 as v4
from scripts import cross_lingual_relation_audit as v1
from scripts import source_reference_chains_v06 as v6
from scripts import typed_partial_relations as v2

VERSION = "particle_attachment_audit_v0.7"
TARGET = r"(?<!\w)(?:" + v1.TARGET + r")(?!\w)"
OWNERS = [
    TARGET + r"\s+(?:(?:colloidal|aggregate)\s+)?particles?\b",
    r"\bparticles?\s+of\s+" + TARGET,
    r"\bparticles?\s+in\s+(?:(?:a|the)\s+)?" + TARGET + r"\s+dispersions?\b",
    r"\bчастиц\w*\s+(?:[А-ЯЁ]{2,6}\s+)?" + TARGET,
    r"\bчастиц\w*\s+дисперси\w*\s+" + TARGET,
]
PROPERTY = re.compile(
    r"\b(?:(?:lamellar(?:-type)?|cylindrical|spherical)\s+(?:structures?|morpholog\w*)|"
    r"morpholog\w*|shapes?|морфолог\w*|форм[аыуеой]*)\b", re.I,
)
MEDIUM = re.compile(
    r"^\s*(?:in\s+(?:(?:[\w:/()–-]+)\s+){0,8}(?P<dispersion>dispersions?)\b"
    r"|в\s+(?P<ru_dispersion>дисперси\w*)\b|in\s+(?:dilute\s+)?(?P<liquid>liquid\s+media)\b)", re.I,
)
HAVE_FORM = re.compile(r"\b(?:(?:were|are)\s+(?:shown\s+to\s+)?have|"
                       r"(?:(?:do|does|did)\s+(?:not\s+)?)?forms?)\s+(?:(?:a|the)\s+)?$", re.I)
DEPEND = re.compile(
    r"\b(?:(?:is|was|are|were)\s+(?:strongly\s+)?(?:affected|influenced)\s+by|"
    r"depend\w*\s+on|var(?:y|ies|ied)\s+with|chang\w*\s+with|завис\w*\s+от)\b", re.I,
)
ACTIVE = re.compile(r"\b(?:affect(?:s|ed)?|influenc(?:e|es|ed)|chang(?:e|es|ed)|влия\w*|изменя(?:ет|ют|л|ла|ли))\b", re.I)
EXTRA_DEP = re.compile(
    r"\b(?:as\s+a\s+result\s+of|(?:is|was|are|were)\s+determined\s+by|определя(?:ется|ются|лась|лись))\b", re.I,
)
CAUSE = re.compile(r"\b(?:cause\s+(?:of|for)|вызыва\w*|влия\w*)\b", re.I)
HYPOTHESIS = re.compile(r"\b(?:likely|probably|possible|possibly|seems?|вероятн\w*|возможн\w*)\b", re.I)
UNPERFORMED = re.compile(r"\bno\s+attempt\b|\bне\s+предпринимал\w*", re.I)
NOT_FORM = re.compile(r"\b(?:do|does|did)\s+not\s+form\b|\bне\s+образу\w*", re.I)
OBSERVATION = re.compile(v1.OBSERVATION.pattern + r"|\bindicat\w*\b", re.I)
COMPOSITION = re.compile(r"\b(?:dispersing\s+fluid|solvent)\s+(?:composition|nature)\b", re.I)


def _status(text: str) -> str:
    if UNPERFORMED.search(text):
        return "unperformed"
    if HYPOTHESIS.search(text):
        return "uncertain"
    status = v1._status(text)
    if NOT_FORM.search(text) and status == "affirmative_assertion_unverified":
        return "observed_null_shape_unverified" if OBSERVATION.search(text) else "bare_negation_unresolved"
    return status


def source_audit(raw: str, query: dict[str, Any]) -> dict[str, Any]:
    view = v1.matching_view(raw)
    units = []
    for a, b in v2.regions(view.text):
        text = view.text[a:b]
        owner_matches = [m for p in OWNERS for m in re.finditer(p, text, re.I)]
        owner_matches = sorted({(m.start(), m.end()): m for m in owner_matches}.values(), key=lambda m: (m.start(), -m.end()))
        owner_matches = [m for m in owner_matches if not any(n.start() <= m.start() < m.end() <= n.end()
                                                           and (n.start(), n.end()) != (m.start(), m.end()) for n in owner_matches)]
        properties = list(PROPERTY.finditer(text))
        if not owner_matches and not properties:
            continue
        owners = [view.anchor(a + m.start(), a + m.end()) for m in owner_matches]
        props = [view.anchor(a + m.start(), a + m.end()) for m in properties]
        media, links, profile_predicates = [], [], []
        for owner in owner_matches:
            candidates = [(owner.end(), text[owner.end():])]
            inside = re.search(r"\bin\b|дисперси\w*", owner.group(), re.I)
            if inside:
                media.append({"kind": "explicit_dispersion", "span": view.anchor(a + owner.start(), a + owner.end())})
            for prop in properties:
                bridge = text[owner.end():prop.start()] if owner.end() <= prop.start() else text[prop.end():owner.start()]
                direct = (
                    owner.end() <= prop.start() and not bridge.strip()
                    or prop.end() <= owner.start() and bool(re.fullmatch(r"\s+(?:(?:evolution\s+)?of\s+(?:the\s+)?)?", bridge, re.I))
                )
                have = HAVE_FORM.search(bridge) if owner.end() <= prop.start() else None
                if have:
                    prefix = bridge[:have.start()].strip()
                    if prefix and (not re.match(r"^(?:in|в)\s", prefix, re.I)
                                   or re.search(r"\b(?:and|и)\s+\w+\s*$", prefix, re.I)):
                        have = None
                if direct or have:
                    links.append({"owner_span": view.anchor(a + owner.start(), a + owner.end()),
                                  "property_span": view.anchor(a + prop.start(), a + prop.end()),
                                  "basis": "direct_syntax" if direct else "explicit_have_form_predicate"})
                    if have:
                        profile_predicates.append(view.anchor(a + owner.end() + have.start(), a + owner.end() + have.end()))
                    if direct and owner.end() <= prop.start():
                        candidates.append((prop.end(), text[prop.end():]))
            for offset, suffix in candidates:
                medium = MEDIUM.search(suffix)
                if medium:
                    media.append({"kind": "liquid_media_surface" if medium["liquid"] else "explicit_dispersion",
                                  "span": view.anchor(a + offset + medium.start(), a + offset + medium.end())})
        variables = v2.variable_nodes(view, a, b)
        composition = [{"kind": "dispersing_fluid_composition", "span": view.anchor(a + m.start(), a + m.end()),
                        "solvent_binding": "explicit_lexical", "value_owner_established": False}
                       for m in COMPOSITION.finditer(text)]
        variables = [n for n in variables if not any(c["span"]["start"] <= n["span"]["start"]
                                                   < n["span"]["end"] <= c["span"]["end"] for c in composition)] + composition
        directions = []
        for prop in properties:
            for variable in variables:
                va, vb = v4._offsets(view, variable["span"])
                va, vb = va - a, vb - a
                if prop.end() <= va:
                    start, end, direction = prop.end(), va, "property_depends_on_variable"
                    pred = DEPEND.search(text[start:end]) or EXTRA_DEP.search(text[start:end])
                elif vb <= prop.start():
                    start, end, direction = vb, prop.start(), "variable_affects_property"
                    pred = ACTIVE.search(text[start:end]) or CAUSE.search(text[start:end])
                    if re.search(r"\b(?:is|was|are|were)\s+(?:strongly\s+)?(?:affected|influenced)\s+by\b", text[start:end], re.I):
                        pred = None
                else:
                    continue
                if pred:
                    tail = text[start + pred.end():end].strip()
                    allowed_tail = (
                        r"(?:the|a|an|(?:the\s+)?(?:changes?\s+in|nature\s+of|composition\s+of)(?:\s+the)?|"
                        r"increased|decreased|changing|varying|природ\w*)?"
                        if direction == "property_depends_on_variable" else r"(?:the)?"
                    )
                    if not re.fullmatch(allowed_tail, tail, re.I):
                        continue
                    directions.append({"direction": direction, "property_span": view.anchor(a + prop.start(), a + prop.end()),
                                       "variable": variable,
                                       "predicate_span": view.anchor(a + start + pred.start(), a + start + pred.end())})
        status = _status(text)
        diagnostics = []
        if len(owners) != 1 or len(list(re.finditer(v1.PARTICLE, text, re.I))) != 1:
            diagnostics.append("particle_owner_missing_or_multiple")
        if len(props) != 1 or len(links) != 1:
            diagnostics.append("property_attachment_missing_or_multiple")
        if re.search(r"\b(?:membranes?|films?|мембран\w*|пл[её]н\w*)\b", text, re.I):
            diagnostics.append("competing_membrane_or_film")
        if v6.HEADING.search(text):
            diagnostics.append("section_heading_in_source_unit")
        if v2.OTHER_PROPERTY.search(text):
            diagnostics.append("competing_other_property")
        if status not in {"affirmative_assertion_unverified", "observed_null_effect_unverified", "observed_null_shape_unverified"}:
            diagnostics.append("statement_status_not_eligible")
        if v4.EVIDENCE_ABSENCE.search(text) or v4.NEGATIVE_OBSERVATION.search(text):
            diagnostics.append("absence_or_negative_observation")
        if len(variables) > 1:
            diagnostics.append("multiple_variables_unresolved")
        attached = bool(links) and len(owners) == 1 and len(props) == 1
        eligible = attached and not diagnostics
        directed = bool(directions) and len(directions) == 1 and len(variables) == 1
        dispersion = any(m["kind"] == "explicit_dispersion" for m in media)
        solvent = len(variables) == 1 and (
            variables[0]["kind"] in {"literal_solvent", "dispersing_fluid_composition"}
            or variables[0]["kind"] == "named_component_ratio" and variables[0]["solvent_binding"] == "explicit_lexical"
        )
        kind = "directed_dependency" if directed else "shape_description" if profile_predicates else "morphology_description"
        units.append({
            "span": view.anchor(a, b), "particle_owners": owners, "properties": props, "medium_attachments": media,
            "particle_property_links": links, "profile_predicates": profile_predicates, "directions": directions,
            "variables": variables, "status": status, "relation_kind": kind, "eligible_particle_relation": eligible,
            "role_links_complete": eligible and dispersion and (directed or bool(profile_predicates)),
            "requested_requirements_met": eligible and dispersion and directed and solvent
            and not query["constraints"] and not query["unsupported_query_tokens"],
            "diagnostics": diagnostics, "fields": v1.field_spans(view, a, b),
            "scientific_admission": False, "chemical_identity_established": False, "performed_established": False,
            "material_owner_established": False, "value_owner_established": False,
        })
    return {"units": units, "scientific_admission": False}


def audit(question: str, sources: list[dict[str, Any]], *, baseline_adequate: bool) -> dict[str, Any]:
    result = v6.audit(question, sources, baseline_adequate=baseline_adequate)
    result["version"] = VERSION
    analyses, relations, groups = [], [], {}
    if result["requirements"]["in_scope"]:
        for index, source in enumerate(sources):
            analysis = source_audit(source["text"], result["requirements"])
            analyses.append({"evidence_index": index, **analysis})
            for position, unit in enumerate(analysis["units"]):
                if unit["eligible_particle_relation"]:
                    address = {"evidence_index": index, "unit_index": position}
                    relations.append({**address, "role_links_complete": unit["role_links_complete"],
                                      "requested_requirements_met": unit["requested_requirements_met"], "scientific_admission": False})
                    groups.setdefault(hashlib.sha256(unit["span"]["text"].encode()).hexdigest(), []).append(address)
    result.update(atomic_sources=analyses, particle_relations=relations,
                  particle_requirements_met=any(r["requested_requirements_met"] for r in relations)
                  if result["requirements"]["in_scope"] else None,
                  exact_particle_groups=[{"raw_unit_sha256": digest, "addresses": addresses} for digest, addresses in groups.items()])
    return result
