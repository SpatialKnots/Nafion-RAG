"""Finite adjacent-statement dependency proposals, never runtime admission."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import asdict
from typing import Any, cast

from scripts.requested_context_links import (
    _CUES,
    _SAMPLE,
    SourceEvidence,
    SourcePage,
    _page_anchors,
    _sample_key,
    audit_links,
)
from scripts.requested_information_audit import Span

VERSION = "experiment_sentence_links_v0.1"
_REFERENCE = re.compile(
    r"\b(?:before\s+this|for\s+(?:this|the\s+same))\s+(?:gravimetric\s+|impedance\s+|conductivity\s+)?measurement\b|"
    r"\b(?:перед\s+этим|для\s+этого|для\s+того\s+же)\s+измерени\w*", re.I)
_SPECTRA = re.compile(r"^\s*(?:спектры\s+за[-\s]*писывал\w*|spectra\s+were\s+recorded)\b", re.I)
_MEASUREMENT = re.compile(r"\b(?:measur\w*|измер[яе]\w*)\b", re.I)
_ASSERTION = re.compile(r"\b(?:measured|измерял\w*|измерен\w*)\b|measurements\s+were\s+(?:performed|conducted)", re.I)
_OTHER_WORK = re.compile(r"\b(?:another\s+(?:work|study)|different\s+(?:work|study)|друг\w*\s+(?:работ\w*|исследован\w*))\b", re.I)


def statement_units(text: str) -> list[Span]:
    """New sidecar boundaries; semicolons after instrument numbers still split.

    Decimal points remain inside units. Earlier frozen splitter is unchanged.
    This finite punctuation splitter does not claim linguistic sentence parsing.
    """
    result, start = [], 0
    for match in re.finditer(r"\.(?!\d)(?:\s+|$)|[!?;](?:\s+|$)|\n\s*\n", text):
        if text[start:match.end()].strip():
            result.append(Span(start, match.end(), text[start:match.end()]))
        start = match.end()
    if text[start:].strip():
        result.append(Span(start, len(text), text[start:]))
    return result


def dependencies(evidence: SourceEvidence, pages: Sequence[SourcePage]) -> dict[str, object]:
    """One-chunk directed graph. Nodes do not pool values, samples or conditions."""
    # Reuse unchanged provenance validation from the earlier prototype.
    audit_links("Inspect context", [], [evidence], pages)
    units = statement_units(evidence.text)
    nodes: list[dict[str, Any]] = []
    for index, unit in enumerate(units):
        nodes.append({"id": index, "span": asdict(unit), "cues": [key for key, pattern in _CUES.items()
                                                                   if re.search(pattern, unit.text, re.I)],
                      "samples": sorted({_sample_key(m.group()) for m in _SAMPLE.finditer(unit.text)}),
                      "page_anchors": _page_anchors(evidence, unit.text, pages)})
    attempts: list[dict[str, Any]] = []
    for index in range(1, len(nodes)):
        parent, child = nodes[index - 1], nodes[index]
        raw_parent, raw_child = units[index - 1].text, units[index].text
        reference = _REFERENCE.search(raw_child)
        spectra = _SPECTRA.search(raw_child)
        if reference is None and spectra is None:
            continue
        marker = reference if reference is not None else spectra
        assert marker is not None
        kind = "explicit_measurement_reference" if reference is not None else "impedance_instrument_to_recorded_spectra"
        reasons = []
        parent_cues, child_cues = set(parent["cues"]), set(child["cues"])
        if re.search(r"\n\s*\n", raw_parent):
            reasons.append("paragraph_boundary")
        if not _MEASUREMENT.search(raw_parent):
            reasons.append("parent_measurement_not_explicit")
        if not _ASSERTION.search(raw_parent) and not ("impedance" in parent_cues and re.search(
                r"использовал\w*|\bused\b", raw_parent, re.I)):
            reasons.append("parent_measurement_assertion_unresolved")
        if _REFERENCE.search(raw_parent):
            reasons.append("referential_parent_not_new_operation")
        if re.search(r"\b(?:if|unless|если|при\s+условии)\b", raw_parent + raw_child, re.I):
            reasons.append("conditional_context_unresolved")
        if not parent_cues.intersection({"conductivity", "swelling", "impedance", "gravimetry"}):
            reasons.append("parent_operation_type_unresolved")
        if kind == "impedance_instrument_to_recorded_spectra" and (
                "impedance" not in parent_cues or not re.search(r"использовал\w*|\bused\b", raw_parent, re.I)):
            reasons.append("parent_impedance_instrument_not_explicit")
        for key in ("preparation", "drying", "soaking", "negation", "hypothesis"):
            if key in parent_cues or key in child_cues:
                reasons.append(key + "_boundary_or_ambiguity")
        if _OTHER_WORK.search(raw_parent) or _OTHER_WORK.search(raw_child):
            reasons.append("other_work_reference")
        if len(parent["samples"]) > 1 or len(child["samples"]) > 1:
            reasons.append("mixed_sample_labels")
        elif parent["samples"] and child["samples"] and parent["samples"] != child["samples"]:
            reasons.append("competing_sample_labels")
        for group in ({"conductivity", "swelling"}, {"impedance", "gravimetry"}):
            pc, cc = parent_cues & group, child_cues & group
            if len(pc) > 1 or len(cc) > 1:
                reasons.append("mixed_property_or_method")
            elif pc and cc and pc != cc:
                reasons.append("competing_property_or_method")
        if len(parent["page_anchors"]) != 1 or len(child["page_anchors"]) != 1:
            reasons.append("unique_exact_parent_child_anchors_unresolved")
        attempts.append({"parent": index - 1, "child": index, "kind": kind,
                         "bridge_span": {"start": units[index].start + marker.start(),
                                         "end": units[index].start + marker.end(), "text": marker.group()},
                         "separator_kind": "semicolon_clauses" if raw_parent.rstrip().endswith(";") else "sentence_units",
                         "state": "blocked_or_unresolved" if reasons else "dependency_proposal_unverified",
                         "diagnostics": sorted(set(reasons)),
                         "sample_identity": "repeated_literal_label_only" if parent["samples"] == child["samples"] and
                         parent["samples"] else "not_established",
                         "temporal_relation": "before_explicit" if reference and re.match(
                             r"before|перед", reference.group(), re.I) else "not_established",
                         "scientific_relation": "not_evaluated", "values_and_conditions_propagated": False})
    return {"version": VERSION, "citation_id": evidence.citation_id, "article_id": evidence.article_id,
            "chunk_id": evidence.chunk_id, "nodes": nodes, "attempts": attempts,
            "unlinked_unit_ids": [n["id"] for n in nodes if not any(
                a["state"] == "dependency_proposal_unverified" and n["id"] in {a["parent"], a["child"]} for a in attempts)],
            "scientific_relation": "not_evaluated", "runtime_action": "none_offline_only"}


def attach_dependencies(baseline: dict[str, object], evidence: Sequence[SourceEvidence],
                        pages: Sequence[SourcePage]) -> dict[str, object]:
    """Sidecar only: baseline scientific statuses and answer data remain unchanged."""
    graphs = [dependencies(e, pages) for e in evidence]
    attachments = []
    for index, candidate in enumerate(cast(list[dict[str, Any]], baseline["source_candidates"])):
        links = []
        for graph in graphs:
            if graph["citation_id"] != candidate["citation_id"]:
                continue
            nodes = cast(list[dict[str, Any]], graph["nodes"])
            for attempt_id, attempt in enumerate(cast(list[dict[str, Any]], graph["attempts"])):
                child = nodes[attempt["child"]]["span"]
                if child["start"] <= candidate["value"]["start"] < candidate["value"]["end"] <= child["end"]:
                    links.append({"attempt_id": attempt_id, "state": attempt["state"], "kind": attempt["kind"]})
        attachments.append({"source_candidate_index": index, "dependency_attempts": links,
                            "baseline_state": candidate["state"], "coverage_upgrade": False})
    return {"version": VERSION, "graphs": graphs, "candidate_dependencies": attachments,
            "baseline_modified": False, "scientific_coverage": "not_evaluated",
            "limitations": ["finite_adjacent_templates", "no_transitive_or_skipping_links", "no_value_or_condition_inheritance",
                            "no_general_coreference", "dependency_proposals_not_scientific_confirmation"]}
