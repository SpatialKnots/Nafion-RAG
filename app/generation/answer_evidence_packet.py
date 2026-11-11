"""Canonical diagnostic evidence snapshots and replayable observation journals."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.evaluation.query_packet import aligned_pages
from app.generation.answer_facts import VERSION as FACT_VERSION
from app.generation.answer_requirements import VERSION as REQUIREMENTS_VERSION
from app.generation.answer_requirements import _raw_sources, validate_requirements
from app.generation.fact_types import Anchor, verify_anchor
from app.generation.methods_identity import POLICY as METHODS_POLICY
from app.generation.preparation import VERSION as PREPARATION_VERSION
from app.generation.providers import Evidence
from app.records.schema import SourceRegion, text_hash
from app.records.sources import file_hash

VERSION = "answer_evidence_packet_v0.1"
PARENT_VERSION = "answer_requirements_preparation_v0.1"
JOURNAL_VERSION = "answer_diagnostic_journal_v0.1"
CODE_FILES = ("app/generation/answer_evidence_packet.py", "app/generation/evidence_packet_routes.py",
    "app/generation/answer_requirements.py", "app/generation/requirements_routes.py", "app/generation/preparation.py",
    "app/generation/preparation_routes.py", "app/generation/fact_types.py", "app/generation/fact_recipes.py",
    "app/generation/source_paraphrases.py", "app/generation/reference_quotes.py", "app/generation/source_role_assembly.py",
    "app/generation/methods_identity.py", "app/generation/answer_facts.py", "app/generation/service.py",
    "app/generation/providers.py", "app/evaluation/query_packet.py", "app/records/schema.py", "app/core/config.py")
ANCHOR_KEYS = tuple(Anchor.__dataclass_fields__)


def serialize_packet(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _hash(value: dict[str, Any]) -> str:
    return text_hash(serialize_packet(value).decode("utf-8"))


def code_bindings() -> dict[str, str]:
    root = Path(__file__).resolve().parents[2]
    return {name: file_hash(root / name) for name in CODE_FILES}


def _anchors(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        if set(ANCHOR_KEYS) <= value.keys():
            return [{k: value[k] for k in ANCHOR_KEYS}]
        return [a for v in value.values() for a in _anchors(v)]
    if isinstance(value, list):
        return [a for v in value for a in _anchors(v)]
    return []


def _page_index(preparation: dict[str, Any]) -> tuple[list[dict[str, Any]], list[SourceRegion]]:
    regions = [SourceRegion.model_validate(r) for r in preparation["sources"].get("pages", {}).values()]
    positions: set[tuple[str, int, str]] = set()
    originals: dict[str, tuple[str, str]] = {}
    layers: dict[tuple[str, str], tuple[str, str]] = {}
    selected = preparation["evidence"]
    for region in regions:
        article, layer = str(region.article_id), region.text_layer
        position = (article, region.page_number, layer)
        if position in positions:
            raise ValueError("Duplicate registered page identity in evidence packet")
        positions.add(position)
        possible = [e for e in selected if e["article_id"] == article and e["page_start"] <= region.page_number <= e["page_end"]]
        known = {preparation["sources"]["chunk_layers"].get(e["chunk_id"]) for e in possible} - {None}
        if not possible or (known and layer not in known):
            raise ValueError("Foreign page or layer outside selected evidence packet scope")
        original = (region.original_pdf_path, region.original_pdf_sha256)
        chosen = (region.layer_pdf_path, region.layer_pdf_sha256)
        if (article in originals and originals[article] != original) or ((article, layer) in layers and layers[(article, layer)] != chosen):
            raise ValueError("Conflicting PDF identity in registered evidence packet pages")
        originals[article], layers[(article, layer)] = original, chosen
    pages = []
    for region in regions:
        descriptor = {k: v for k, v in region.model_dump(mode="json").items()
                      if k not in {"page_text", "quote", "quote_sha256", "start", "end", "selection_note"}}
        pages.append({"id": "P:" + _hash(descriptor), **descriptor, "pdf_integrity": "declared_snapshot_not_freshly_read"})
    return sorted(pages, key=lambda p: p["id"]), regions


def _page_spans(anchor: dict[str, Any], source: Evidence, regions: list[SourceRegion], pages: list[dict[str, Any]],
                layer: str) -> list[dict[str, Any]]:
    selected = [r for r in regions if str(r.article_id) == source.article_id and r.text_layer == layer
                and source.page_start <= r.page_number <= source.page_end]
    mapping = aligned_pages(source, selected, layer)
    spans = []
    for region, offset, left in mapping:
        if len(mapping) > 1 and not offset <= anchor["start"] < anchor["end"] <= offset + len(region.page_text.strip()):
            continue
        start, end = left + anchor["start"] - offset, left + anchor["end"] - offset
        if 0 <= start < end <= len(region.page_text) and region.page_text[start:end] == anchor["text"]:
            page = next(p for p in pages if p["region_id"] == region.region_id)
            spans.append({"page_ref": page["id"], "start": start, "end": end,
                          "text": anchor["text"], "page_text_sha256": region.page_text_sha256})
    if len(spans) > 1:
        raise ValueError("Ambiguous exact page mapping for evidence packet anchor")
    return spans


def _journal(content: dict[str, Any]) -> dict[str, Any]:
    events: list[dict[str, Any]] = []

    def record(kind: str, input_hash: str, output_hash: str, reason: str, details: dict[str, Any]) -> None:
        event = {"sequence": len(events) + 1, "kind": kind, "actor_kind": "deterministic_system",
            "previous_hash": events[-1]["event_hash"] if events else None, "input_hash": input_hash, "output_hash": output_hash,
            "reason": reason, "details": details, "action_executed": False, "scientific_support": "not_evaluated"}
        events.append({**event, "event_hash": _hash(event)})

    parent = content["parent"]
    record("preparation_observed", content["parent_hash"], _hash(parent["preparation"]), "original_preparation_preserved",
        {"status": parent["preparation"]["status"], "blocking_reasons": parent["preparation"]["blocking_reasons"],
         "retrieval_history_reconstructed": False})
    mapped = parent["requirements"]
    record("requirements_reconstructed", _hash(parent["preparation"]), _hash(mapped), mapped["status"],
        {"version": mapped["version"], "reason": mapped["reason"], "selection_changed": False, "admission_changed": False})
    for row in mapped["requirements"]:
        refs = next(r for r in content["requirements"] if r["id"] == row["id"])
        record("requirement_state_observed", _hash(mapped), _hash(row), row["state"],
            {"requirement_ref": row["id"], "fact_refs": refs["fact_refs"], "anchor_refs": refs["anchor_refs"],
             "diagnostics": row.get("diagnostics", []), "contracts": row.get("contracts", []),
             "unknown_fields": row.get("unknown_fields", []), "proposed_next_action": row["next_action"]})
    record("read_only_stop_observed", _hash(mapped), _hash(content["stop"]), "diagnostic_boundary_no_action_authorized",
           content["stop"])
    return {"version": JOURNAL_VERSION, "events": events, "root_hash": events[-1]["event_hash"],
            "human_reviews": [], "timing_recorded": False, "meaning": "system_observations_not_executed_retrieval_or_human_review"}


def build_packet(parent: dict[str, Any]) -> dict[str, Any]:
    if (parent.get("version") != PARENT_VERSION or not isinstance(parent.get("preparation"), dict)
            or not isinstance(parent.get("requirements"), dict)
            or any(parent.get(k) is not False for k in ("generation_performed", "external_request_constructed", "network_ready"))):
        raise ValueError("Evidence packet requires explicit no-generation requirement preparation")
    preparation, mapped = parent["preparation"], parent["requirements"]
    validate_requirements(mapped, preparation, mapped.get("request_scope"))
    bindings = code_bindings()
    raw, missing, restored = _raw_sources(preparation)
    layers = preparation["sources"]["chunk_layers"]
    sources = []
    for source in raw:
        identity = {"citation_id": source.citation_id, "article_id": source.article_id, "chunk_id": source.chunk_id,
            "page_start": source.page_start, "page_end": source.page_end, "source_type": source.source_type,
            "text_layer": layers[source.chunk_id], "raw_chunk_sha256": text_hash(source.text)}
        sources.append({"id": "S:" + _hash(identity), **identity, "raw_text": source.text})
    sources.sort(key=lambda s: s["id"])
    source_by_chunk = {s["chunk_id"]: s for s in sources}
    raw_by_chunk = {s.chunk_id: s for s in raw}
    pages, regions = _page_index(preparation)
    anchors: dict[str, dict[str, Any]] = {}
    for data in _anchors(mapped):
        raw_source = raw_by_chunk.get(data["chunk_id"])
        if raw_source is None:
            raise ValueError("Evidence packet anchor references an uninspected raw source")
        verify_anchor(Anchor(**data), raw_source)
        key = "A:" + _hash(data)
        spans = _page_spans(data, raw_source, regions, pages, layers[raw_source.chunk_id])
        anchors[key] = {"id": key, "source_ref": source_by_chunk[raw_source.chunk_id]["id"], "anchor": data,
            "page_spans": spans, "page_binding": "exact_single_page_mapping" if spans else "exact_page_mapping_unresolved"}
    facts, transformations, requirements = [], [], []
    for row in mapped["requirements"]:
        fact_refs = []
        for candidate in row.get("candidates", []):
            candidate_refs = []
            for fact in candidate["facts"]:
                descriptor = {"requirement_ref": row["id"], "source_ref": source_by_chunk[candidate["chunk_id"]]["id"],
                    "support_ref": "A:" + _hash(fact["support"]), "fact": deepcopy(fact)}
                key = "F:" + _hash(descriptor)
                facts.append({"id": key, **descriptor})
                candidate_refs.append(key)
                fact_refs.append(key)
            if candidate["arithmetic"] is not None:
                descriptor = {"requirement_ref": row["id"], "input_fact_refs": candidate_refs,
                    "arithmetic": deepcopy(candidate["arithmetic"]), "validation": "existing_recipe_reconstructed_from_raw"}
                transformations.append({"id": "T:" + _hash(descriptor), **descriptor})
        requirements.append({"id": row["id"], "state": row["state"], "source_state": row["source_state"],
            "support_state": row["support_state"], "scientific_support": "not_evaluated", "fact_refs": fact_refs,
            "anchor_refs": sorted({"A:" + _hash(a) for a in _anchors(row)})})
    content = {"parent": deepcopy(parent), "parent_hash": _hash(parent), "request_scope": deepcopy(mapped["request_scope"]),
        "versions": {"packet": VERSION, "requirements": REQUIREMENTS_VERSION, "preparation": PREPARATION_VERSION,
            "facts": FACT_VERSION, "methods_policy_available_not_enabled_by_packet": METHODS_POLICY,
            "code_bindings": bindings, "code_scope": "fixed_declared_packet_dependencies_not_complete_runtime_environment"},
        "sources": sources, "pages": pages, "anchors": sorted(anchors.values(), key=lambda a: a["id"]),
        "facts": facts, "transformations": transformations, "requirements": requirements, "claims": [],
        "inspection": {"uninspected": missing, "restored_derived_parents": restored,
            "anchor_observations": len(_anchors(mapped)), "unique_anchors": len(anchors)},
        "stop": {"baseline_status": preparation["status"], "baseline_blocking_reasons": deepcopy(preparation["blocking_reasons"]),
            "new_source_actions_executed": 0, "model_calls_executed": 0, "generation_performed": False,
            "scientific_support": "not_evaluated", "reason": "read_only_diagnostic_boundary"}}
    journal = _journal(content)
    core = {"version": VERSION, "content": content, "journal": journal}
    if bindings != code_bindings():
        raise ValueError("Evidence packet code changed during construction")
    return {**core, "packet_id": _hash(core), "scientific_support": "not_evaluated", "generation_performed": False,
            "external_request_constructed": False, "network_ready": False}


def validate_packet(packet: dict[str, Any], current_parent: dict[str, Any], *, expected_packet_id: str | None = None) -> None:
    if expected_packet_id is not None and packet.get("packet_id") != expected_packet_id:
        raise ValueError("Evidence packet differs from pinned snapshot identity")
    if serialize_packet(packet) != serialize_packet(build_packet(current_parent)):
        raise ValueError("Evidence packet/code/source/journal differs from current-parent reconstruction")


def save_packet(path: Path, packet: dict[str, Any], current_parent: dict[str, Any]) -> None:
    """Explicit local export only; no endpoint accepts this path or overwrites files."""
    validate_packet(packet, current_parent)
    with path.open("xb") as stream:
        stream.write(serialize_packet(packet))
        stream.flush()
        os.fsync(stream.fileno())


def load_packet(path: Path, current_parent: dict[str, Any], *, expected_packet_id: str | None = None) -> dict[str, Any]:
    raw = path.read_bytes()
    packet = json.loads(raw)
    if not isinstance(packet, dict) or serialize_packet(packet) != raw:
        raise ValueError("Evidence packet export is not canonical UTF-8 JSON")
    validate_packet(packet, current_parent, expected_packet_id=expected_packet_id)
    return packet
