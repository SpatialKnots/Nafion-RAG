"""Source-coordinate table accounting, deliberately conservative about shared cells."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from app.records.multi import MultiReply
from app.records.schema import CandidateBundle, SourceRegion, text_hash
from app.records.spans import TokenSpan, resolve_token_span, token_offsets

VERSION = "records_table_cells_v0.1"
NUMERIC = re.compile(r"\d+(?:[.,]\d+)?(?:\s*×\s*10[–−-]?\d+)?")


def absolute_span(bundle: CandidateBundle, span: TokenSpan) -> dict[str, Any]:
    selected = resolve_token_span(bundle, span)
    region = next(r for r in bundle.regions if r.region_id == selected.region_id)
    return {"region_id": region.region_id, "start": region.start + selected.start,
            "end": region.start + selected.end, "text": selected.quote}


def token_address(region: SourceRegion, start: int, end: int, *, label: str = "R1") -> dict[str, Any]:
    offsets = token_offsets(region.quote)
    starts = {left: i for i, (left, _) in enumerate(offsets)}
    ends = {right: i for i, (_, right) in enumerate(offsets)}
    if start - region.start not in starts or end - region.start not in ends:
        raise ValueError("Source cell does not align with selectable token endpoints")
    return {"region": label, "start_token": starts[start - region.start], "end_token": ends[end - region.start]}


def _center(line: dict[str, Any]) -> float:
    return (float(line["bbox"][0]) + float(line["bbox"][2])) / 2


def _overlap(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return bool(min(a["bbox"][3], b["bbox"][3]) > max(a["bbox"][1], b["bbox"][1]))


def _evidence(line: dict[str, Any]) -> dict[str, Any]:
    # Only trailing/leading whitespace is excluded from a selectable raw cell.
    text = line["text"]
    start = line["page_start"] + len(text) - len(text.lstrip())
    end = line["page_start"] + len(text.rstrip())
    return {"start": start, "end": end, "text": text.strip(), "bbox": line["bbox"], "block_number": line["block_number"]}


def build_cell_ledger(page: dict[str, Any], region: SourceRegion) -> dict[str, Any]:
    """Two-column sigma table proposal, not a general table parser or a gold standard."""
    if (page["article_id"] != str(region.article_id) or page["page_number"] != region.page_number
            or page["page_text_sha256"] != region.page_text_sha256 or page["page_text"] != region.page_text
            or page["text_layer_id"] != str(region.text_layer_id)
            or page["original_pdf_sha256"] != region.original_pdf_sha256):
        raise ValueError("Table source identity differs from registered page")
    gaps = page["source_gaps"]
    if not gaps["text_geometry_proven"]:
        raise ValueError("Table source text/geometry correspondence is unproven")
    groups = [g for g in page["protected_groups"] if g["kind"] == "closed_ruled_table_proposal"]
    if len(groups) != 1:
        raise ValueError("Expected exactly one protected ruled table proposal")
    group = groups[0]
    if any(not region.start <= left < right <= region.end for left, right in group["page_ranges"]):
        raise ValueError("Protected table is clipped by source context")
    lines = []
    for line in gaps["lines"]:
        start, end = line["page_start"], line["page_end"]
        box = line["bbox"]
        if (not 0 <= start < end <= len(region.page_text) or region.page_text[start:end] != line["text"]
                or text_hash(line["text"]) != line["text_sha256"] or len(box) != 4
                or not all(math.isfinite(x) for x in box) or box[2] <= box[0] or box[3] <= box[1]):
            raise ValueError("Invalid registered line text/hash/geometry")
        if line["block_number"] in group["block_numbers"]:
            lines.append(line)
    sample_headers = [line for line in lines if line["text"].strip() == "№ образца"]
    headers = sorted([line for line in lines if re.fullmatch(r"σ[–−-]?\d+°C,", line["text"].strip())], key=_center)
    if len(sample_headers) != 1 or len(headers) != 2:
        raise ValueError("Unsupported table sample/sigma headers")
    sample_header = sample_headers[0]
    half_width = (_center(headers[1]) - _center(headers[0])) / 2
    columns: list[dict[str, Any]] = []
    for i, header in enumerate(headers):
        center = _center(header)
        units = [line for line in lines if line["text"].strip() == "См см–1"
                 and abs(_center(line) - center) < half_width and line["bbox"][1] >= header["bbox"][1]]
        if len(units) != 1:
            raise ValueError("Missing or ambiguous conductivity column unit")
        columns.append({"index": i, "center": center, "half_width": half_width,
                        "header": _evidence(header), "unit": _evidence(units[0])})
    labels = sorted([line for line in lines if re.fullmatch(r"\d+", line["text"].strip())
                     and sample_header["bbox"][0] <= _center(line) <= sample_header["bbox"][2]
                     and line["bbox"][1] > sample_header["bbox"][3]], key=lambda line: line["page_start"])
    if not labels or [int(line["text"].strip()) for line in labels] != list(range(1, len(labels) + 1)):
        raise ValueError("Sample row labels are missing, repeated or out of order")
    counts = Counter(line["block_number"] for line in labels)
    slots = []
    for label in labels:
        for column in columns:
            candidates = [line for line in lines if line["block_number"] == label["block_number"]
                          and abs(_center(line) - column["center"]) < half_width
                          and (counts[label["block_number"]] > 1 or _overlap(line, label))]
            if counts[label["block_number"]] > 1:
                state = "unresolved_shared_block"
            elif len(candidates) != 1:
                state = "unresolved_missing_or_multiple"
            elif candidates[0]["text"].strip() in {"–", "—", "-", "−"}:
                state = "explicit_dash"
            elif NUMERIC.fullmatch(candidates[0]["text"].strip()):
                state = "numeric_source_proposal"
            else:
                state = "unresolved_syntax"
            evidence = [_evidence(line) for line in candidates]
            raw = evidence[0] if state in {"numeric_source_proposal", "explicit_dash"} else None
            identity = [VERSION, region.region_id, label["page_start"], column["header"]["start"]]
            slots.append({"cell_id": text_hash(str(identity)), "row": int(label["text"].strip()),
                          "column": column["index"], "source_state": state, "sample": _evidence(label),
                          "header": column["header"], "unit": column["unit"], "value": raw,
                          "related_lines": evidence, "previous_proposals": []})
    summary = dict(Counter(s["source_state"] for s in slots))
    summary.update(logical_slots=len(slots), rows=len(labels), columns=len(columns))
    return {"version": VERSION, "article_id": str(region.article_id), "region_id": region.region_id,
            "original_pdf_path": region.original_pdf_path, "original_pdf_sha256": region.original_pdf_sha256,
            "page": region.page_number, "text_layer": region.text_layer, "text_layer_id": str(region.text_layer_id),
            "page_text_sha256": region.page_text_sha256, "protected_group": group, "slots": slots, "summary": summary,
            "scientific_reference": "not_established", "shared_cell_ownership": "unresolved"}


def bind_reply(bundle: CandidateBundle, reply: MultiReply, ledger: dict[str, Any], *,
               targets: list[str] | None = None, require_method_region: bool = False) -> list[str]:
    """Bind exact value + row + column coordinates; identical lexemes cannot substitute."""
    if len(bundle.regions) < 1 or bundle.regions[0].region_id != ledger["region_id"]:
        raise ValueError("Reply table region differs from ledger")
    target_set = set(targets) if targets is not None else {s["cell_id"] for s in ledger["slots"]}
    if targets is not None and len(target_set) != len(targets):
        raise ValueError("Duplicate declared target")
    bound: list[str] = []
    for item in reply.measurements:
        obs = {str(o.field): o for o in item.observations}
        raw = obs["value"].raw_span
        if raw is None:
            raise ValueError("Table proposal has no source value")
        value = absolute_span(bundle, raw)
        matches = [s for s in ledger["slots"] if s["source_state"] == "numeric_source_proposal"
                   and value["region_id"] == ledger["region_id"]
                   and (value["start"], value["end"]) == (s["value"]["start"], s["value"]["end"])]
        if len(matches) != 1 or matches[0]["cell_id"] not in target_set:
            raise ValueError("Value does not identify one declared unambiguous numeric source cell")
        cell = matches[0]
        if cell["cell_id"] in bound:
            raise ValueError("Duplicate proposed table cell")
        for field, reference, exact in (("sample_label", "sample", True), ("temperature", "header", False), ("unit", "unit", True)):
            span = obs[field].raw_span
            if span is None:
                raise ValueError(f"Table proposal missing {field} source coordinates")
            actual, expected = absolute_span(bundle, span), cell[reference]
            inside = expected["start"] <= actual["start"] < actual["end"] <= expected["end"]
            if (actual["region_id"] != ledger["region_id"] or not inside
                    or (exact and (actual["start"], actual["end"]) != (expected["start"], expected["end"]))):
                raise ValueError(f"Wrong table {field} row/column/source coordinates")
            if field == "temperature" and actual["text"].lstrip("σ") != expected["text"].rstrip(",").lstrip("σ"):
                raise ValueError("Temperature selection omits or changes printed column temperature")
        method = obs["method"]
        if require_method_region and method.status == "present":
            if (len(bundle.regions) != 2 or bundle.regions[1].article_id != bundle.regions[0].article_id
                    or method.raw_span is None or method.raw_span.region != "R2"):
                raise ValueError("Present method must cite same-article R2")
            link = item.linkage.conditions_measurement
            if link is None or {s.region for s in link.evidence} != {"R1", "R2"}:
                raise ValueError("Present method requires table + method conditions-measurement evidence")
        bound.append(cell["cell_id"])
    return bound
