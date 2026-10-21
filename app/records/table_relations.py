"""Versioned source-coordinate/cue audit; scientific relationships remain unassessed."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from app.records.fixed_links import FixedSpanMeasurement
from app.records.schema import CandidateBundle, SourceRegion
from app.records.table_cells import absolute_span, build_cell_ledger

VERSION = "records_table_relations_v0.1"
MIXTURE = re.compile(r"Смеси (?P<components>[A-Za-z0-9]+(?:/[A-Za-z0-9]+)+)")
METHOD = re.compile(r"импедансной\s+спектроскопии")


def _span(line: dict[str, Any], region: SourceRegion) -> dict[str, Any]:
    raw = line["text"]
    start = line["page_start"] + len(raw) - len(raw.lstrip())
    end = line["page_start"] + len(raw.rstrip())
    return {"region_id": region.region_id, "start": start, "end": end, "text": region.page_text[start:end],
            "bbox": line["bbox"], "block_number": line["block_number"]}


def _inside(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    return bool(actual["region_id"] == expected["region_id"]
                and expected["start"] <= actual["start"] < actual["end"] <= expected["end"])


def _exact(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    return _inside(actual, expected) and (actual["start"], actual["end"]) == (expected["start"], expected["end"])


def relation_map(page: dict[str, Any], ledger: dict[str, Any], table: SourceRegion) -> dict[str, Any]:
    regenerated = build_cell_ledger(page, table)
    if len(regenerated["slots"]) != len(ledger["slots"]):
        raise ValueError("Relation audit source-cell inventory differs from frozen ledger")
    for original, current in zip(regenerated["slots"], ledger["slots"], strict=True):
        if any(current.get(key) != value for key, value in original.items() if key != "previous_proposals"):
            raise ValueError("Relation audit source geometry differs from frozen ledger")
    lines = [line for line in page["source_gaps"]["lines"]
             if line["block_number"] in ledger["protected_group"]["block_numbers"]]
    headers = [line for line in lines if line["text"].strip() == "пластификатора"]
    header = headers[0] if len(headers) == 1 else None
    basis_lines = [line for line in lines if line["text"].strip() == "(масс. доли)" and header is not None
                   and header["bbox"][0] <= (line["bbox"][0] + line["bbox"][2]) / 2 <= header["bbox"][2]]
    basis = _span(basis_lines[0], table) if len(basis_lines) == 1 else None
    labels = {s["sample"]["start"]: s["sample"] for s in ledger["slots"]}
    block_rows = Counter(label["block_number"] for label in labels.values())
    groups: list[dict[str, Any]] = []
    for line in lines:
        label_tops = [label["bbox"][1] for label in labels.values() if label["block_number"] == line["block_number"]]
        is_section = bool(label_tops and line["bbox"][3] <= min(label_tops))
        raw = line["text"].strip()
        if not (is_section or raw.startswith("Смеси ") or raw == "Индивидуальные растворители"):
            continue
        evidence = _span(line, table)
        match = MIXTURE.fullmatch(raw)
        kind = "mixture" if match else "individual" if raw == "Индивидуальные растворители" else "unsupported"
        components = None
        if match:
            components = {**evidence, "start": evidence["start"] + match.start("components"), "text": match.group("components")}
        groups.append({"kind": kind, "source": evidence, "components": components})
    rows = {}
    for cell in ledger["slots"]:
        sample = cell["sample"]
        eligible = [g for g in groups if g["source"]["bbox"][3] <= sample["bbox"][1]]
        nearest_y = max((g["source"]["bbox"][3] for g in eligible), default=None)
        nearest = [g for g in eligible if g["source"]["bbox"][3] == nearest_y]
        group = nearest[0] if len(nearest) == 1 and nearest[0]["kind"] != "unsupported" else None
        candidates = [line for line in lines if header is not None and line["block_number"] == sample["block_number"]
                      and header["bbox"][0] <= (line["bbox"][0] + line["bbox"][2]) / 2 <= header["bbox"][2]
                      and min(line["bbox"][3], sample["bbox"][3]) > max(line["bbox"][1], sample["bbox"][1])]
        composition = _span(candidates[0], table) if len(candidates) == 1 and block_rows[sample["block_number"]] == 1 else None
        medium = group["components"] if group and group["kind"] == "mixture" else (
            composition if group and group["kind"] == "individual" else None)
        rows[cell["cell_id"]] = {"sample": {**sample, "region_id": table.region_id}, "composition": composition,
                                 "plasticiser_header": _span(header, table) if header else None, "basis": basis,
                                 "group": group, "nearby_group_candidates": nearest, "medium_label": medium,
                                 "composition_candidates": [_span(line, table) for line in candidates],
                                 "shared_block": block_rows[sample["block_number"]] > 1}
    return {"version": VERSION, "source_region_id": table.region_id, "groups": groups, "cells": rows,
            "header_state": "unique_literal_cue" if header else "missing_or_ambiguous_literal_cue",
            "basis_state": "unique_literal_cue" if basis else "missing_or_ambiguous_literal_cue",
            "scientific_semantics": "not_evaluated"}


def finding(rule: str, outcome: str, reason: str, *, actual: Any = None, expected: Any = None) -> dict[str, Any]:
    return {"rule": rule, "outcome": outcome, "reason": reason, "actual": actual, "expected": expected,
            "scientific_support": "not_evaluated"}


def audit_measurement(bundle: CandidateBundle, measurement: FixedSpanMeasurement, cell: dict[str, Any],
                      relations: dict[str, Any]) -> list[dict[str, Any]]:
    # Reparse source metadata and resolve the actual selected occurrence; never
    # recover a raw address by searching the candidate's text inside broad evidence.
    bundle = CandidateBundle.model_validate_json(bundle.model_dump_json())
    selected = {str(o.field): absolute_span(bundle, o.raw_span) if o.raw_span else None for o in measurement.observations}
    observations = {str(o.field): o for o in measurement.observations}
    expected = relations["cells"][cell["cell_id"]]
    result = []
    table_id = relations["source_region_id"]
    for field, key in (("sample_label", "sample"), ("value", "value")):
        reference = expected["sample"] if key == "sample" else ({**cell["value"], "region_id": table_id} if cell["value"] else None)
        actual = selected[field]
        outcome = "not_proposed" if actual is None else "unsupported_source_layout" if reference is None else (
            "coordinates_match" if _exact(actual, reference) else "different_source_coordinates")
        result.append(finding(f"{field}.cell", outcome, "Literal coordinate binding only, not experimental identity.",
                              actual=actual, expected=reference))
    for field, key in (("medium_composition", "composition"), ("medium", "medium_label"), ("composition_basis", "basis")):
        actual, reference = selected[field], expected[key]
        if actual is None:
            outcome = "not_proposed"
        elif reference is None:
            outcome = "unsupported_source_layout"
        elif field == "composition_basis":
            inner = {**reference, "start": reference["start"] + 1, "end": reference["end"] - 1}
            outcome = "coordinates_match" if _inside(actual, reference) and _inside(inner, actual) else "different_source_coordinates"
        else:
            outcome = "coordinates_match" if _exact(actual, reference) else "different_source_coordinates"
        result.append(finding(f"{field}.source_label", outcome,
                              "Printed plasticiser column/group/basis only. "
                              "No environment, membrane composition or chemical identity inferred.",
                              actual=actual, expected=reference))
    chain = {"sample": expected["sample"], "composition": expected["composition"],
             "plasticiser_header": expected["plasticiser_header"], "basis": expected["basis"]}
    if expected["group"] and expected["group"]["kind"] == "mixture":
        chain["component_group"] = expected["group"]["source"]
    citations = [absolute_span(bundle, s) for s in observations["medium_composition"].evidence]
    absent = [name for name, endpoint in chain.items() if endpoint is None or not any(_inside(endpoint, cited) for cited in citations)]
    chain_outcome = "not_proposed" if selected["medium_composition"] is None else (
        "unsupported_source_layout" if any(s is None for s in chain.values()) or expected["group"] is None else
        "endpoints_covered" if not absent else "citation_endpoint_not_covered")
    result.append(finding("composition.citation_chain", chain_outcome,
                          "Field citations checked separately; other fields may cite omitted endpoints. "
                          "This is not a scientific error label.",
                          actual={"citations": citations, "uncovered_endpoints": absent}, expected=chain))
    method = selected["method"]
    if method is None:
        method_outcome = "not_proposed"
    else:
        region = next(r for r in bundle.regions if r.region_id == method["region_id"])
        table = next(r for r in bundle.regions if r.region_id == table_id)
        same_article = region.article_id == table.article_id and region.original_pdf_sha256 == table.original_pdf_sha256
        method_outcome = ("literal_method_cue" if same_article and region.page_number != table.page_number
                          and METHOD.search(method["text"]) else "unsupported_method_source_or_wording")
    result.append(finding("method.literal_source", method_outcome,
                          "Same-article, different-page method cue only; applicability and paragraph completeness remain unknown.",
                          actual=method))
    roles = {"sample_value": ("sample_label", "value"), "property_value": ("property_name", "value"),
             "conditions_measurement": ("temperature", "value", "method") if method else ("temperature", "value")}
    for role, fields in roles.items():
        link = getattr(measurement.linkage, role)
        citations = [absolute_span(bundle, s) for s in link.evidence] if link else []
        endpoints = {name: selected[name] for name in fields}
        missing = [name for name, endpoint in endpoints.items() if endpoint is None or not any(_inside(endpoint, s) for s in citations)]
        outcome = ("not_proposed" if link is None else "unresolved_missing_endpoint" if any(s is None for s in endpoints.values()) else
                   "endpoints_covered" if not missing else "citation_endpoint_not_covered")
        result.append(finding(f"linkage.{role}.endpoint_coverage", outcome,
                              "Coverage of selected coordinates does not establish scientific support for this linkage role.",
                              actual={"citations": citations, "uncovered_endpoints": missing}, expected=endpoints))
    result.append(finding("composition.semantic_scope", "unknown",
                          "Source label says plasticiser composition. "
                          "Mapping to measurement environment/final membrane is not established.",
                          expected=expected["plasticiser_header"]))
    result.append(finding("method.applicability", "unknown",
                          "A general article method is not an independently validated per-result method."))
    return result


def history_comparisons(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(record["cell_id"], []).append(record)
    differences = []
    for cell_id, entries in grouped.items():
        if len(entries) < 2:
            continue
        fields = sorted({name for row in entries for name in row["selected_fields"]})
        changed = [name for name in fields if len({json_signature(row["selected_fields"].get(name)) for row in entries}) > 1]
        differences.append({"cell_id": cell_id, "candidate_versions": [row["record_id"] for row in entries],
                            "changed_fields": changed, "proposals": [{"stage": row["stage"], "record_id": row["record_id"],
                                "region_ids": row["region_ids"], "fields": {name: row["selected_fields"].get(name) for name in changed}}
                                for row in entries],
                            "interpretation": "Different proposals/source contexts, "
                            "not confirmed conflicting facts or independent experiments."})
    return differences


def json_signature(value: Any) -> str:
    import json

    return json.dumps(value, sort_keys=True, ensure_ascii=False)
